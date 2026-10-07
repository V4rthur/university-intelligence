# 1-bosqich. Biznes muammosi va talablar

## Muammo

Universitetda talabalar, baholar, davomat, to'lov va topshiriqlar haqidagi ma'lumotlar turli
fayl va tizimlarda saqlanadi. Natijada:

1. **Yagona manzara yo'q.** Rahbariyat «hozir nima bo'lyapti?» degan savolga tez va bir xil javob ololmaydi.
2. **Qarorlar kech qabul qilinadi.** Muammo (davomat pasayishi, fandan ommaviy yiqilish) semestr
   yakunida, oqibatlari yuz bergandan keyin ko'rinadi.
3. **Xavf ostidagi talaba kech aniqlanadi.** Talaba o'qishni tashlagach yoki akademik qarzdor
   bo'lgach aralashuv samarasi past bo'ladi.
4. **Qaror ta'siri oldindan baholanmaydi.** «Tyutorlik dasturi nimani o'zgartiradi?» degan savolga
   raqam bilan javob yo'q.

## Biznes maqsadlari

| Savol | Tahlil darajasi | Tizimdagi javob |
|---|---|---|
| Hozir nima bo'lyapti? | Tavsifiy (descriptive) | KPI, salomatlik bali, fakultet va fan ko'rsatkichlari |
| Nima sababdan? | Diagnostik | Chuqurlashish (drill-down), anomaliyalar, omillar tahlili |
| Kelajakda nima bo'ladi? | Bashoratli (predictive) | Talaba xavfi modeli, keyingi semestr GPA bashorati |
| Nima qilish kerak? | Tavsiyaviy (prescriptive) | «Agar...» ssenariylari, alertlar, AI agent tavsiyalari |

## Foydalanuvchilar va ularning ehtiyoji

| Rol | Ehtiyoj | Kirish huquqi |
|---|---|---|
| Universitet rahbariyati | Umumiy holat, fakultetlar taqqoslamasi, qaror ta'siri | To'liq |
| Fakultet dekani | O'z fakulteti, xavf ostidagi talabalar ro'yxati | Faqat o'z fakulteti |
| Professor-o'qituvchi | Fan va yuklama ko'rsatkichlari | Faqat umumlashtirilgan ma'lumot |

## Funksional talablar

- Xom fayllarni (CSV, Excel, JSON) avtomatik o'qish, tozalash, tekshirish va omborga yuklash.
- Konveyerni qayta ishga tushirish dublikat yaratmasligi; yangi ma'lumot qo'shilganda tizim yangilanishi.
- Yulduz sxemali ma'lumotlar ombori (SQL Server).
- Sodda boshqaruv paneli: har bir sahifa bitta savolga javob beradi (7 sahifa), jumladan oraliq va
  yakuniy nazorat natijalari tahlili.
- Haqiqiy baholash tizimiga moslik: 100 ballik tizim, 5/4/3/2 baholar, o'tish bali 60, davomat qoidasi.
- Talaba akademik xavfini bashorat qiluvchi va **nima uchunligini tushuntiruvchi** model.
- 5 ta tayyor va erkin sozlanadigan «agar...» ssenariylari.
- Faqat ombor va model natijalariga tayanadigan AI agent.

## Nofunksional talablar va cheklovlar

- Veb-dasturlash (HTML/CSS/JavaScript) talab qilinmaydi: interfeys sof Pythonda (Streamlit).
- Asosiy texnologiyalar: Python, Pandas, NumPy, SQL Server, Scikit-learn.
- Ma'lumotlar o'zbek tilida; interfeys o'zbek tilida.
- Sintetik ma'lumot ochiq ko'rsatiladi; korrelyatsiya sabab sifatida talqin qilinmaydi.
- Talaba shaxsiy ma'lumotlari rolga qarab yopiladi.

## Muvaffaqiyat mezonlari

| Mezon | Qanday tekshiriladi |
|---|---|
| ETL takroriy ishga tushganda 0 ta yangi yozuv | `etl.LoadAudit` jadvali |
| Model xavf ostidagi talabalarning taxminan 80% ini topadi (chegara validatsiyada recall ≥ 80% bo'ladigan qilib tanlanadi) | `ml.ModelMetrics`, sinov semestri |
| Dashboard va agent bir xil raqam beradi | Ikkalasi ham `05_Analytics/metrics.py` dan foydalanadi |
| Yangi semestr 1-2 daqiqada tizimda ko'rinadi | `run_pipeline.py --new-semester` |
| 5-10 daqiqalik jonli demo | `05_Demo_ssenariy.md` |
