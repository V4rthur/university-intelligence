"""Uzbek reference data used by the synthetic data generator."""

# name, dean, established, annual tuition (so'm), base effect, trend per semester
FACULTIES = [
    ("Iqtisodiyot", "Rahimov Baxtiyor Odilovich", 1994, 16_000_000, -0.30, -0.11),
    ("Biznes va menejment", "Yusupova Dilnoza Karimovna", 2003, 18_000_000, 0.00, 0.0),
    ("Muhandislik", "Toshpo'latov Sardor Anvarovich", 1991, 15_000_000, 0.05, 0.045),
    ("Axborot texnologiyalari", "Ismoilov Jahongir Rustamovich", 2008, 20_000_000, 0.22, 0.0),
    ("Filologiya va tillar", "Qodirova Nargiza Shavkatovna", 1992, 12_000_000, 0.10, 0.0),
    ("Huquq", "Nazarov Ulug'bek Hamidovich", 1998, 22_000_000, -0.05, 0.0),
]
FACULTY_CODES = ["IQ", "BM", "MH", "AT", "FL", "HQ"]   # used in academic group names
YES_NO = ("Ha", "Yo'q")
FACULTY_SHARE =[0.20, 0.18, 0.20, 0.20, 0.12, 0.10]
FEMALE_SHARE = [0.48, 0.52, 0.22, 0.30, 0.78, 0.50]

# three departments per faculty, in faculty order
DEPARTMENTS = [
    "Iqtisodiyot nazariyasi", "Moliya va kredit", "Buxgalteriya hisobi va audit",
    "Menejment", "Marketing", "Xalqaro biznes",
    "Mexanika muhandisligi", "Elektr energetikasi", "Qurilish muhandisligi",
    "Dasturiy injiniring", "Sun'iy intellekt va ma'lumotlar tahlili",
    "Kompyuter tizimlari va tarmoqlar",
    "O'zbek filologiyasi", "Ingliz filologiyasi", "Tarjimashunoslik",
    "Fuqarolik huquqi", "Jinoyat huquqi", "Xalqaro huquq",
]

# general courses taken by every faculty: (name, host DepartmentID), two per
# curriculum semester, in semester order
GENERAL_COURSES = [
    ("Oliy matematika I", 7), ("Xorijiy til (ingliz) I", 14),
    ("Oliy matematika II", 7), ("Xorijiy til (ingliz) II", 14),
    ("O'zbekistonning eng yangi tarixi", 13), ("Axborot texnologiyalari asoslari", 12),
    ("Falsafa", 13), ("Ehtimollar nazariyasi va statistika", 11),
    ("Akademik yozuv", 13), ("Iqtisodiyot asoslari", 1),
    ("Huquqshunoslik asoslari", 16), ("Loyiha boshqaruvi", 4),
    ("Tadbirkorlik asoslari", 6), ("Ilmiy tadqiqot metodologiyasi", 11),
    ("Kasbiy etika", 16), ("Mehnat muhofazasi", 9),
]

# faculty-specific courses: 24 per faculty = 3 per curriculum semester; the
# i-th course of each triple belongs to the i-th department of the faculty
FACULTY_COURSES = [
    [  # Iqtisodiyot
        "Mikroiqtisodiyot", "Moliya asoslari", "Buxgalteriya hisobi asoslari",
        "Makroiqtisodiyot", "Pul va banklar", "Iqtisodiy matematika",
        "Ekonometrika", "Korporativ moliya", "Moliyaviy hisob",
        "Iqtisodiy ta'limotlar tarixi", "Soliqlar va soliqqa tortish", "Boshqaruv hisobi",
        "Xalqaro iqtisodiyot", "Bank ishi", "Audit asoslari",
        "Raqamli iqtisodiyot", "Investitsiyalar tahlili", "Moliyaviy tahlil",
        "Davlat moliyasi", "Sug'urta ishi", "Xalqaro moliyaviy hisobot standartlari",
        "Iqtisodiy siyosat", "Moliya bozorlari", "Ichki audit",
    ],
    [  # Biznes va menejment
        "Menejment asoslari", "Marketing asoslari", "Biznesga kirish",
        "Tashkiliy xulq-atvor", "Iste'molchi xulq-atvori", "Xalqaro biznes asoslari",
        "Inson resurslarini boshqarish", "Marketing tadqiqotlari", "Biznes statistikasi",
        "Operatsion menejment", "Raqamli marketing", "Tashqi iqtisodiy faoliyat",
        "Strategik menejment", "Brend boshqaruvi", "Xalqaro savdo",
        "Innovatsion menejment", "Sotuvlarni boshqarish", "Logistika va ta'minot zanjiri",
        "Sifat menejmenti", "Reklama va jamoatchilik bilan aloqalar", "Xalqaro marketing",
        "Biznes-reja tuzish", "Elektron tijorat", "Madaniyatlararo menejment",
    ],
    [  # Muhandislik
        "Muhandislik grafikasi", "Fizika I", "Materialshunoslik",
        "Nazariy mexanika", "Fizika II", "Qurilish materiallari",
        "Materiallar qarshiligi", "Elektrotexnika asoslari", "Geodeziya",
        "Mashina detallari", "Elektr zanjirlari nazariyasi", "Qurilish mexanikasi",
        "Termodinamika", "Elektr mashinalari", "Temir-beton konstruksiyalar",
        "Gidravlika", "Elektr ta'minoti", "Zamin va poydevorlar",
        "Avtomatik boshqaruv nazariyasi", "Qayta tiklanuvchi energiya manbalari",
        "Qurilish texnologiyasi",
        "Ishlab chiqarishni loyihalash", "Energiya tejamkorligi",
        "Bino va inshootlarni loyihalash",
    ],
    [  # Axborot texnologiyalari
        "Dasturlash asoslari", "Diskret matematika", "Kompyuter arxitekturasi",
        "Obyektga yo'naltirilgan dasturlash", "Chiziqli algebra", "Operatsion tizimlar",
        "Ma'lumotlar tuzilmasi va algoritmlar", "Ma'lumotlar bazasi", "Kompyuter tarmoqlari",
        "Veb-dasturlash", "Ma'lumotlar tahlili", "Tarmoq xavfsizligi",
        "Dasturiy ta'minot injiniringi", "Mashinali o'qitish", "Bulutli texnologiyalar",
        "Mobil ilovalar yaratish", "Chuqur o'qitish", "Tizimli administratsiyalash",
        "Dasturiy ta'minotni testlash", "Katta ma'lumotlar", "Kiberxavfsizlik",
        "DevOps amaliyoti", "Tabiiy tilni qayta ishlash", "Taqsimlangan tizimlar",
    ],
    [  # Filologiya va tillar
        "Tilshunoslikka kirish", "Ingliz tili amaliy fonetikasi", "Tarjima nazariyasi asoslari",
        "O'zbek adabiyoti tarixi", "Ingliz tili grammatikasi", "Yozma tarjima amaliyoti",
        "Hozirgi o'zbek adabiy tili", "Leksikologiya", "Og'zaki tarjima amaliyoti",
        "Adabiyot nazariyasi", "Stilistika", "Qiyosiy tilshunoslik",
        "O'zbek dialektologiyasi", "Ingliz adabiyoti tarixi", "Sinxron tarjima",
        "Matn tahlili", "Tilni o'qitish metodikasi", "Badiiy tarjima",
        "Jahon adabiyoti", "Lingvokulturologiya", "Ilmiy-texnik tarjima",
        "Nutq madaniyati", "Amerika adabiyoti", "Tarjima tanqidi",
    ],
    [  # Huquq
        "Davlat va huquq nazariyasi", "Huquqni muhofaza qiluvchi organlar",
        "Xalqaro huquq asoslari",
        "Fuqarolik huquqi I", "Jinoyat huquqi I", "Konstitutsiyaviy huquq",
        "Fuqarolik huquqi II", "Jinoyat huquqi II", "Inson huquqlari",
        "Oila huquqi", "Kriminologiya", "Xalqaro ommaviy huquq",
        "Mehnat huquqi", "Jinoyat protsessi", "Xalqaro xususiy huquq",
        "Fuqarolik protsessi", "Kriminalistika", "Yevropa Ittifoqi huquqi",
        "Tadbirkorlik huquqi", "Jinoyat-ijroiya huquqi", "Xalqaro savdo huquqi",
        "Intellektual mulk huquqi", "Sud ekspertizasi", "Xalqaro arbitraj",
    ],
]

MALE_NAMES = [
    "Aziz", "Bekzod", "Sardor", "Jasur", "Otabek", "Sherzod", "Ulug'bek", "Farrux",
    "Dilshod", "Rustam", "Anvar", "Bobur", "Javohir", "Islom", "Abdulloh", "Muhammad",
    "Shohruh", "Nodir", "Elyor", "Sanjar", "Temur", "Akmal", "Doston", "Oybek",
    "Kamron", "Asadbek", "Diyorbek", "Zafar", "Humoyun", "Ibrohim", "Mirzo", "Laziz",
    "Samandar", "Xurshid", "Behruz", "Firdavs",
]
FEMALE_NAMES = [
    "Dilnoza", "Madina", "Nigora", "Gulnoza", "Shahzoda", "Malika", "Zarina", "Sevara",
    "Nargiza", "Feruza", "Kamola", "Mohira", "Dildora", "Nilufar", "Gulshan", "Shahlo",
    "Ozoda", "Umida", "Mavluda", "Sitora", "Lola", "Iroda", "Munisa", "Robiya",
    "Fotima", "Zuhra", "Hilola", "Durdona", "Mubina", "Charos", "Sabina", "Asal",
    "Parizoda", "Ruxshona", "Yulduz", "Barno",
]
LAST_NAMES = [
    "Karimov", "Rahimov", "Yusupov", "Toshpo'latov", "Ismoilov", "Qodirov", "Nazarov",
    "Abdullayev", "Xolmatov", "Ergashev", "Sobirov", "Mirzayev", "Umarov", "Hamidov",
    "Saidov", "Rasulov", "Usmonov", "Normatov", "Jo'rayev", "Aliyev", "Tursunov",
    "Olimov", "Sharipov", "Mahmudov", "Boboyev", "Xudoyberdiyev", "Salimov", "Zokirov",
    "Haydarov", "Murodov", "Azimov", "G'aniyev", "Eshonqulov", "Po'latov", "Shodiyev",
    "Valiyev", "Qosimov", "Turg'unov", "Xasanov", "Musayev",
]

GENDER = ("Erkak", "Ayol")
TUITION_STATUS = ("Grant", "Kontrakt")
SCHOLARSHIP = ("Stipendiya oladi", "Stipendiyasiz")
STUDENT_STATUS = ("Faol", "Chetlashtirilgan", "Bitirgan")
DEGREES = ("Magistr", "PhD", "Fan doktori (DSc)")
EMPLOYMENT = ("To'liq stavka", "Yarim stavka", "Soatbay")
COURSE_TYPE = ("Majburiy", "Tanlov")
SEMESTER_NAMES = ("Kuz", "Bahor")
ATTENDANCE = ("Keldi", "Kelmadi", "Sababli")
PAYMENT_STATUS = ("To'liq to'langan", "Qisman to'langan", "To'lanmagan")
SUBMISSION = ("Topshirildi", "Kechikib topshirildi", "Topshirilmadi")
WARNING_TYPES = (
    "Past o'zlashtirish", "Davomat pastligi", "Akademik qarzdorlik", "To'lov qarzdorligi",
)
SEVERITY = ("O'rta", "Yuqori")
