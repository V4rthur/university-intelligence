"""University Intelligence AI Agent (PHASE 10).

An LLM with tool calling: the model decides which tools to call, reads their
JSON results and writes a grounded, structured answer. It is not a chatbot
answering from memory - the system prompt forbids any number that did not
come from a tool result, and the UI shows the tool trace for every answer.

Needs Claude API credentials (environment variable ANTHROPIC_API_KEY).
Without them, `offline_answer()` still answers a fixed set of management
questions directly from the tools, so the demo never depends on the network.

CLI:  python 07_AI_Agent/agent.py "Qaysi fakultetda akademik xavf eng yuqori?"
"""
import os
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from agent_tools import ROLES, TOOLS, Toolbox  # noqa: E402

MAX_TOOL_ROUNDS = 12

SYSTEM_PROMPT = """You are the analytical assistant of the "University Intelligence & AI Decision System", a decision-support system for university management (rector's office, deans, academic staff). Your readers are managers who will act on what you say, so accuracy matters more than fluency.

# Where your facts come from
You have tools that read the university's SQL Server data warehouse, the analytics layer, the machine-learning risk model and the what-if simulation engine. They are your only source of facts about this university.
- Every number, name, ranking or trend in your answer must come from a tool result in this conversation. If you have not called a tool that returns it, call one before answering.
- If the tools cannot provide what is asked (the data does not exist, the period is not covered, a tool returns an error or a permission denial), say so plainly and say what data would be needed. Do not estimate, extrapolate or fill gaps from general knowledge.
- Prefer the specialised tools; use sql_query only for questions they cannot answer.

# Honesty about what the data can support
- The data is synthetic, generated to resemble a real university. Never describe it as real university data. Mention this once when you give recommendations or a report.
- A risk probability is a model estimate for the next semester, not a guarantee about any student.
- The data shows associations. Do not state that one factor causes another; say what moves together and what would need to be checked. Scenario results are model-based estimates under stated assumptions - always repeat the assumptions.
- "Possible reason" hints from the anomaly tool are leads for investigation, not conclusions.

# Access control
The user's role is given below. A tool may refuse with "RUXSAT YO'Q" (no permission). When that happens, tell the user this information is not available for their role and offer the aggregated view instead. Never try to obtain restricted information another way (for example through SQL).

# How to answer
Answer in the language the question was asked in (Uzbek by default). Use this structure for analytical questions, in that language, and keep each part short:

**SAVOL:** the question restated in one line
**JAVOB:** the direct answer in one or two sentences
**Asosiy ko'rsatkichlar:** 3-6 bullet points with the exact figures from the tools
**Asosiy sabablar / omillar:** what the data shows about why (only if the tools support it)
**TAVSIYA:** concrete, prioritised actions tied to the figures above - who should do what for which group
**Ishonchlilik:** Yuqori / O'rta / Past, with one line of justification based on the evidence (sample size, model recall, whether the effect is an assumption). Do not invent a percentage.

For simple factual questions a short direct answer is enough. For recommendations, where it would help, run scenario_simulation to quantify the expected effect before recommending an intervention. When asked to prepare a report, gather the facts first, then call generate_report with the finished text and tell the user where it was saved."""


def has_credentials() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


class UniversityAgent:
    def __init__(self, toolbox: Toolbox | None = None, role: str = "rahbariyat",
                 own_faculty: str | None = None):
        self.toolbox = toolbox or Toolbox(role=role, own_faculty=own_faculty)
        self.client = anthropic.Anthropic()
        self.messages: list[dict] = []
        scope = f" Fakultet: {own_faculty}." if own_faculty else ""
        self.system = [
            {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": f"Current user role: {ROLES[self.toolbox.role]['label']} "
                                     f"({self.toolbox.role}).{scope}"},
        ]

    def ask(self, question: str, on_tool=None) -> dict:
        """Answer one question. Returns {'text', 'tools', 'stop_reason'}."""
        self.messages.append({"role": "user", "content": question})
        first_call = len(self.toolbox.trace)
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                response = self.client.beta.messages.create(
                    model=config.AGENT_MODEL,
                    max_tokens=16000,
                    system=self.system,
                    tools=TOOLS,
                    messages=self.messages,
                    output_config={"effort": "medium"},
                    # if a request is declined, the API re-runs it on a fallback model
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                )
                self.messages.append({"role": "assistant", "content": response.content})
                if response.stop_reason != "tool_use":
                    break
                results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    if on_tool:
                        on_tool(block.name, block.input)
                    payload, is_error = self.toolbox.run(block.name, block.input)
                    results.append({"type": "tool_result", "tool_use_id": block.id,
                                    "content": payload, "is_error": is_error})
                self.messages.append({"role": "user", "content": results})
        except anthropic.AuthenticationError:
            return self._failed("API kaliti noto'g'ri. ANTHROPIC_API_KEY ni tekshiring.", first_call)
        except anthropic.RateLimitError:
            return self._failed("So'rovlar limiti oshdi. Birozdan so'ng qayta urinib ko'ring.", first_call)
        except anthropic.APIStatusError as exc:
            return self._failed(f"API xatosi ({exc.status_code}): {exc.message}", first_call)
        except anthropic.APIConnectionError:
            return self._failed("Tarmoq xatosi: Claude API bilan bog'lanib bo'lmadi.", first_call)

        text = "\n".join(b.text for b in response.content if b.type == "text").strip()
        if response.stop_reason == "refusal":
            text = text or "Model bu so'rovga javob berishdan bosh tortdi."
        elif response.stop_reason == "tool_use":
            text = text or "Javob tayyorlash uchun vositalar chaqiruvi limiti tugadi. Savolni toraytiring."
        return {"text": text, "tools": self.toolbox.trace[first_call:],
                "stop_reason": response.stop_reason}

    def _failed(self, message: str, first_call: int) -> dict:
        # drop the unanswered turn so the conversation can continue cleanly
        while self.messages and not (self.messages[-1]["role"] == "user"
                                     and isinstance(self.messages[-1]["content"], str)):
            self.messages.pop()
        if self.messages:
            self.messages.pop()
        return {"text": message, "tools": self.toolbox.trace[first_call:], "stop_reason": "error"}


# --------------------------------------------------------------- offline mode
OFFLINE_QUESTIONS = {
    "risk_faculty": "Qaysi fakultetda akademik xavf eng yuqori?",
    "top_students": "Xavf darajasi eng yuqori 20 nafar talabani ko'rsat.",
    "top_courses": "Qaysi fanlarda yiqilish darajasi eng yuqori?",
    "attendance_drop": "Davomat 5 foiz punktga pasaysa nima bo'ladi?",
    "intervention": "Xavf ostidagi talabalarga aralashuv qanday natija beradi?",
    "overview": "Universitetda hozir nima bo'lyapti?",
}


def offline_answer(toolbox: Toolbox, key: str) -> dict:
    """Template answers built straight from tool results - no LLM involved."""
    first = len(toolbox.trace)
    q = OFFLINE_QUESTIONS[key]

    def call(name, **args):
        import json
        payload, _ = toolbox.run(name, args)
        return json.loads(payload)

    if key == "risk_faculty":
        r = call("faculty_analytics")
        if "error" in r:
            body = f"**JAVOB:** {r.get('detail', r['error'])}"
        else:
            f = max(r["faculties"], key=lambda x: x.get("HighRiskShare") or 0)
            body = (f"**JAVOB:** Eng yuqori xavf - **{f['FacultyName']}** fakultetida.\n\n"
                    f"**Asosiy ko'rsatkichlar ({r['semester']}):**\n"
                    f"- Yuqori/kritik xavfdagi talabalar: {f['HighRiskStudents']:.0f} nafar "
                    f"({f['HighRiskShare']:.1%})\n- O'rtacha GPA: {f['AvgGPA']:.2f}\n"
                    f"- Davomat: {f['AttendanceRate']:.1%}\n- Yiqilish darajasi: {f['FailureRate']:.1%}\n"
                    f"- Salomatlik bali: {f['HealthScore']} (o'rin: {f['Rank']}/{len(r['faculties'])})")
    elif key == "top_students":
        r = call("student_analytics", action="top_risk", limit=20)
        if "error" in r:
            body = f"**JAVOB:** {r['detail']}"
        else:
            rows = "\n".join(
                f"| {s['StudentKey']} | {s['FullName']} | {s['FacultyName']} | "
                f"{s['RiskProbability']:.0%} | {s['RiskLevel']} | {s['MainFactors']} |"
                for s in r["students"])
            body = ("**JAVOB:** Model bahosi bo'yicha xavfi eng yuqori 20 talaba:\n\n"
                    "| ID | Talaba | Fakultet | Xavf | Daraja | Asosiy omillar |\n|---|---|---|---|---|---|\n"
                    + rows + f"\n\n_{r['note']}_")
    elif key == "top_courses":
        r = call("course_analytics", period="latest", limit=10)
        rows = "\n".join(f"| {c['CourseName']} | {c['FacultyName']} | {c['Enrollment']:.0f} | "
                         f"{c['FailureRate']:.1%} | {c['Difficulty']} |" for c in r["courses"])
        body = (f"**JAVOB:** {r['period']} semestrida yiqilish darajasi eng yuqori fanlar:\n\n"
                "| Fan | Fakultet | Talabalar | Yiqilish | Qiyinlik |\n|---|---|---|---|---|\n" + rows)
    elif key in ("attendance_drop", "intervention"):
        r = call("scenario_simulation",
                 scenario="attendance_drop" if key == "attendance_drop" else "risk_intervention")
        fmt = {"GPA": "{:.2f}", "talabalar": "{:,.0f}"}

        def show(o, v):
            if "GPA" in o["Outcome"]:
                return fmt["GPA"].format(v)
            return fmt["talabalar"].format(v) if "talabalar" in o["Outcome"] else f"{v:.2%}"
        rows = "\n".join(f"| {o['Outcome']} | {show(o, o['Baseline'])} | {show(o, o['Scenario'])} |"
                         for o in r["outcomes"])
        body = (f"**JAVOB:** {r['title']} - {r['students_affected']:,} / {r['students_total']:,} "
                f"talabaga ta'sir qiladi.\n\n**Faraz:** {r['assumptions']}\n\n"
                "| Ko'rsatkich | Hozir | Ssenariy |\n|---|---|---|\n" + rows + f"\n\n_{r['note']}_")
    else:
        r = call("university_overview")
        k = r["kpis"]
        alerts = "\n".join(f"- {a['text']}" for a in r["alerts"]) or "- Faol ogohlantirish yo'q."
        body = (f"**JAVOB:** {k['semester']} semestri holati. Universitet salomatlik bali: "
                f"**{r['health_score']}/100**.\n\n**Asosiy ko'rsatkichlar:**\n"
                f"- Faol talabalar: {k['total_students']:,}\n- O'rtacha GPA: {k['avg_gpa']:.2f}\n"
                f"- Davomat: {k['attendance']:.1%}\n- Yiqilish darajasi: {k['failure_rate']:.1%}\n"
                f"- Yuqori/kritik xavfdagi talabalar: {k['high_risk_students']:,}\n"
                f"- To'lov yig'ilishi: {k['collection_rate']:.1%}\n\n**Ogohlantirishlar:**\n{alerts}")
    return {"text": f"**SAVOL:** {q}\n\n{body}", "tools": toolbox.trace[first:],
            "stop_reason": "offline"}


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or OFFLINE_QUESTIONS["risk_faculty"]
    if has_credentials():
        answer = UniversityAgent().ask(question, on_tool=lambda n, a: print(f"  [tool] {n} {a}"))
    else:
        print("ANTHROPIC_API_KEY topilmadi - oflayn rejim (tayyor savollar).\n")
        answer = offline_answer(Toolbox(), "risk_faculty")
    print(answer["text"])
