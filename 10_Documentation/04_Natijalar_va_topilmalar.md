# Natijalar, topilmalar va tavsiyalar

_Avtomatik yaratilgan: `python 05_Analytics/facts.py`. Joriy semestr: **2026-2027 Kuz**. Ma'lumotlar sintetik; bashoratlar ehtimollik bo'lib, kafolat emas._

## Tizim hajmi

- Talabalar: 13,780 (faol 10,681); o'qituvchilar: 132; fanlar: 160
- Ombordagi fakt yozuvlari: 4,536,519
- Ma'lumotlar sifati bali: 98.89% (4,498,384 yozuv o'qilgan, 2,784 tasi karantinga olingan, 7,925 dublikat olib tashlangan)

## Asosiy ko'rsatkichlar

- Universitet salomatlik bali: **75.9 / 100**
- O'rtacha GPA: 3.84 · davomat: 91.7% · fanlardan yiqilish: 12.4%
- Bitirish darajasi: 91.3% · semestrdan semestrga saqlanish: 98.6%
- To'lov yig'ilishi: 90.2% · jami qarzdorlik: 47.9 mlrd so'm
- Yuqori yoki kritik xavfdagi talabalar: **1,638** (15.3%)

## Imtihon natijalari

Baholash: joriy nazorat 20 + oraliq nazorat 30 + yakuniy nazorat 50 = 100 ball; o'tish bali 60; baholar 5 / 4 / 3 / 2.

- Oraliq nazorat o'rtacha natijasi: 79.6% (o'tganlar 92.3%)
- Yakuniy nazorat o'rtacha natijasi: 79.1% (qo'yilganlar orasida o'tganlar 89.9%)
- Yakuniy nazoratga qo'yilmagan natijalar (davomat qoidasi): 4.2%
- Baholar: 5 - 23.8%, 4 - 49.1%, 3 - 14.7%, 2 - 12.4%
- Oraliq nazoratda 60% dan past olganlarning 72.0% qismi yakuniy nazoratdan ham o'ta olmagan yoki unga qo'yilmagan: oraliq nazorat - erta ogohlantirish belgisi.
- Oraliq nazoratdan o'tgan, lekin fandan yiqilgan natijalar: 6.4%

## Model sifati (keyingi semestrda sinov)

| Model | Chegara | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|---|---|
| Random Forest (tanlangan) | 0.364 | 0.897 | 0.695 | 0.785 | 0.738 | 0.943 |
| Logistic Regression | 0.349 | 0.898 | 0.699 | 0.791 | 0.742 | 0.945 |
| Decision Tree | 0.373 | 0.892 | 0.684 | 0.777 | 0.728 | 0.937 |
| Gradient Boosting | 0.325 | 0.896 | 0.688 | 0.798 | 0.739 | 0.944 |

Tanlangan model xavf ostidagi talabalarning 79% qismini topadi; 418 tasi o'tkazib yuborilgan (False Negative), 670 tasi ortiqcha belgilangan (False Positive). Modellar orasidagi farq kichik - natija bitta algoritmga bog'liq emas.

## Topilmalar

1. **Iqtisodiyot fakulteti eng yuqori xavf zonasida.** Yuqori/kritik xavfdagilar ulushi 22.5% (487 talaba), o'rtacha GPA 3.53, davomat 88.6%. Shu semestr bo'yicha GPA yildan yilga: 3.76 → 3.71 → 3.65 → 3.60 → 3.53.
2. **Xavfni asosan akademik tarix tushuntiradi.** Xavf ostidagi talabalarda omillar ulushi: GPA 78%, Topshiriqlar 9%, Yiqilgan fanlar 8%, Akademik tarix 3%. Davomat va qarzning mustaqil hissasi kichik, chunki ularning ta'siri GPA orqali allaqachon aks etgan.
3. **Anomaliya - Ma'lumotlar tahlili (Axborot texnologiyalari), 2025-2026 Bahor:** yiqilish darajasi odatdagidan keskin yuqori (6.4% → 28.1%, +21.7 f.p.). Yakuniy nazorat natijasi oraliq nazoratga nisbatan ancha ko'p tushgan (-29.9 va -1.2 f.p.) — imtihon murakkabligi yoki baholash mezoni o'zgargan bo'lishi mumkin.
4. **Anomaliya - Biznes va menejment, 2025-2026 Kuz:** davomat keskin oshdi (85.8% → 92.2%, +6.4 f.p.). O'zgarish faqat shu fakultetda kuzatilgan — fakultet ichidagi omil (jadval, o'qituvchilar tarkibi, tashkiliy o'zgarish) bo'lishi mumkin.
5. **Anomaliya - Iste'molchi xulq-atvori (Biznes va menejment), 2024-2025 Bahor:** yiqilish darajasi odatdagidan keskin yuqori (4.4% → 13.9%, +9.4 f.p.). Ballar semestr davomida ham past bo'lgan — fan mazmuni, o'qitish yoki talabalar tayyorgarligidagi o'zgarishni tekshirish kerak.
6. **Anomaliya - Tashkiliy xulq-atvor (Biznes va menejment), 2024-2025 Bahor:** yiqilish darajasi odatdagidan keskin yuqori (8.0% → 15.8%, +7.8 f.p.). Ballar semestr davomida ham past bo'lgan — fan mazmuni, o'qitish yoki talabalar tayyorgarligidagi o'zgarishni tekshirish kerak.
7. **Moliyaviy va akademik xavf birga uchraydi.** «Qarz 60% dan yuqori» guruhida akademik xavf ostidagilar 24.8%, «Qarzi yo'q» guruhida 19.1%. Bu bog'liqlik, sabab-oqibat isboti emas.
8. **O'qituvchi yuklamasi va natijalar o'rtasida sezilarli bog'liqlik topilmadi.** Yuklamani 10% kamaytirish ssenariysi GPA ni +0.00 ga o'zgartiradi (model xatoligi doirasida).

## Ssenariylar natijasi

| Ssenariy | Ta'sir doirasi | GPA | Xavf ostidagilar | Yiqilish | Bitirish ehtimoli |
|---|---|---|---|---|---|
| Davomat 5 foiz punktga pasaysa | 10,681 | -0.04 | +128 | +1.23 f.p. | -1.06 f.p. |
| Talabalarning 30 foiziga tyutorlik dasturi berilsa | 3,204 | +0.06 | -461 | -2.66 f.p. | +0.45 f.p. |
| Xavf ostidagi talabalarga maqsadli aralashuv qilinsa | 1,638 | +0.01 | -30 | -0.60 f.p. | +0.65 f.p. |
| O'qituvchi yuklamasi 10 foizga kamaytirilsa | 10,681 | +0.00 | -6 | -0.01 f.p. | +0.05 f.p. |
| Topshiriqlarni bajarish 15 foiz punktga oshsa | 10,681 | +0.01 | -222 | -0.51 f.p. | +0.25 f.p. |

Farazlar har bir ssenariy uchun dashboardda ko'rsatilgan va sozlanadi.

## Tavsiyalar (ustuvorlik tartibida)

1. **Iqtisodiyot fakultetida maqsadli akademik qo'llab-quvvatlash dasturini boshlash.** Birinchi navbatda 487 nafar yuqori/kritik xavfdagi talaba bilan ishlash; eng qiyin fanlar bo'yicha qo'shimcha konsultatsiyalar.
2. **Xavfi eng yuqori 30% talabaga tyutorlik dasturini pilot sifatida sinash.** Model bahosi: xavf ostidagilar -461 talabaga, yiqilish darajasi -2.66 f.p. ga o'zgaradi. Pilot natijasi simulyatsiya farazlarini haqiqiy raqam bilan almashtiradi.
3. **Yuqori va kritik xavfdagi talabalarga maslahatchi biriktirish.** Model bahosi: yuqori/kritik guruh -258 talabaga o'zgaradi.
4. **Anomaliya aniqlangan fan(lar)da imtihon materiallari va baholash mezonlarini ko'rib chiqish.**
5. **Qarzi katta talabalar bilan moliyaviy maslahat va to'lov jadvalini moslashtirish** - akademik yordam bilan birga, chunki ikkala xavf bir guruhda to'planadi.
6. **Har semestr yakunida ro'yxatni yangilash:** `python run_pipeline.py` - xavf qayta hisoblanadi.

## Kutilayotgan ta'sir

- Xavf ostidagi talabalar semestr yakunida emas, keyingi semestr boshlanishidan oldin aniqlanadi.
- Qarorlar ta'siri oldindan raqam bilan baholanadi; resurslar eng katta samara kutilgan joyga yo'naltiriladi.
- Rahbariyat, dekanat va o'qituvchilar bir xil, yagona manbadagi raqamlar bilan ishlaydi.
- Haqiqiy samara faqat haqiqiy ma'lumot va pilot tajriba asosida tasdiqlanadi.
