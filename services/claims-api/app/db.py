import sqlite3

SEED_CLAIMS = [
    (1001, "m-100", "Office visit", "2024-02-11", 125.00, "PAID"),
    (1002, "m-100", "Lab panel", "2024-03-02", 88.40, "PENDING"),
    (1003, "m-200", "Physical therapy", "2024-03-15", 240.00, "PAID"),
    (1004, "m-200", "Imaging", "2024-04-01", 610.75, "DENIED"),
    (1005, "m-300", "Urgent care", "2024-04-20", 175.00, "PAID"),
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE claims (
            id INTEGER PRIMARY KEY,
            member_id TEXT NOT NULL,
            description TEXT NOT NULL,
            service_date TEXT NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL
        )"""
    )
    conn.executemany("INSERT INTO claims VALUES (?, ?, ?, ?, ?, ?)", SEED_CLAIMS)
    conn.commit()
    return conn


_conn = get_connection()


def db() -> sqlite3.Connection:
    return _conn
