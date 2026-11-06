from pelumas_agent.guards.outbound import (
    FITMENT_FALLBACK,
    PRICE_FALLBACK,
    STOCK_FALLBACK,
    GuardContext,
    run_guards,
)

PRICE_CORPUS = [
    "Harganya Rp 15.000.000 ya pak",
    "Harga BM250 Rp12.500.000",
    "Untuk unit ini harganya 15 juta",
    "Sekitar 8 jt nego tipis",
    "Price-nya IDR 4,500,000",
    "IDR 2500000 per unit",
    "Harganya 2.750.000 sudah termasuk ongkir",
    "Bisa saya kasih harga 150 ribu",
    "USD 1,200 ya",
    "Harga net 9.900.000",
    "Harga grosir Rp 900.000 per pcs",
    "Diskon 10% jadi Rp 13.500.000",
    "Ada potongan 500 ribu",
    "Nego sampai jadi saja pak",
    "Bisa kurang 2 juta kalau ambil banyak",
    "Harga distributor Rp 11.200.000",
    "15.5 juta sudah kirim",
    "Nett 3.250.000 ya",
    "Cashback 200 ribu tersedia",
    "Silakan, harganya Rp 45.000.000 untuk 3 unit",
    "Seharga 3,5 jt sudah pasang",
    "Biayanya Rp 250.000 per pemeriksaan",
    "Total 45 juta untuk semua",
    "Harga spesial 1.850.000 khusus hari ini",
]

STOCK_CORPUS = [
    "Stoknya ready pak",
    "Barang ready stock",
    "Stok tersedia 10 pcs",
    "Masih ada stok di gudang",
    "Unitnya tersedia ya",
    "Ready 4 unit",
    "Stok aman kok",
    "Barangnya ada, siap kirim",
]

FITMENT_CORPUS = [
    "BM250 cocok untuk instalasi Anda",
    "Tenang, pas untuk pipa 2 inch",
    "Kompatibel dengan sistem bapak",
    "Macnaught F100 interchangeable dengan Z-Flo 40",
    "Ini setara dengan LC M40",
    "Identik dengan yang lama",
    "Bisa dipakai langsung tanpa adaptor",
    "Pengganti yang sama persis untuk unit lama Anda",
]

SAFE_CORPUS = [
    "Untuk harga, saya teruskan ke admin ya — sebentar.",
    "Saya cek dulu ketersediaannya ke gudang.",
    "Perlu saya konfirmasi dulu kecocokannya dengan tim teknis.",
    "Berikut spesifikasi Avery Hardoll BM250: sambungan 2 1/2 inch, tekanan maks 10.5 bar.",
    "Kandidat pengganti, perlu konfirmasi teknis: LC M40.",
    "Boleh kirim foto nameplate-nya supaya saya pastikan modelnya?",
    "RFQ RFQ-2026-10-0001 sudah saya teruskan ke admin.",
]


def test_price_corpus_blocked():
    for text in PRICE_CORPUS:
        outcome = run_guards(text)
        assert not outcome.passed, text
        assert outcome.fallback == PRICE_FALLBACK, text


def test_stock_corpus_blocked():
    for text in STOCK_CORPUS:
        outcome = run_guards(text)
        assert not outcome.passed, text
        assert outcome.fallback == STOCK_FALLBACK, text


def test_fitment_corpus_blocked():
    for text in FITMENT_CORPUS:
        outcome = run_guards(text)
        assert not outcome.passed, text
        assert outcome.fallback == FITMENT_FALLBACK, text


def test_safe_corpus_passes():
    for text in SAFE_CORPUS:
        outcome = run_guards(text)
        assert outcome.passed, text


def test_admin_relay_allows_price():
    text = "Penawaran dari admin: Rp 15.000.000"
    assert not run_guards(text).passed
    assert run_guards(text, GuardContext(admin_relay=True)).passed


def test_backed_fitment_passes():
    text = "Berdasarkan evaluasi aturan, unit ini cocok untuk sistem Anda."
    assert run_guards(text, GuardContext(fitment_backed=True)).passed


def test_confirmed_stock_passes():
    text = "Berdasarkan data terakhir, unit ini tersedia."
    assert run_guards(text, GuardContext(stock_confirmed=True)).passed


def test_adversarial_corpus_size():
    assert len(PRICE_CORPUS) + len(STOCK_CORPUS) + len(FITMENT_CORPUS) >= 40
