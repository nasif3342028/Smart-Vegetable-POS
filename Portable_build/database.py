import sqlite3
import os
from datetime import datetime
from app_paths import BASE_DIR


DB_PATH = os.path.join(BASE_DIR, "vegetable_pos.db")


class Database:

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        print(f"[DATABASE] Database path: {self.db_path}")
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                mobile      TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id   INTEGER NOT NULL,
                session_id    TEXT NOT NULL,
                vegetable     TEXT NOT NULL,
                weight_kg     REAL NOT NULL,
                price_per_kg  REAL NOT NULL,
                total_price   REAL NOT NULL,
                created_at    TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            )
        """)

        conn.commit()
        conn.close()
        print("[DATABASE] Tables initialized successfully.")

    def generate_session_id(self):
        now = datetime.now()
        return now.strftime("SES-%Y%m%d-%H%M%S")

    def save_session(self, customer_info, cart_items):
        if not cart_items:
            print("[DATABASE] No cart items to save.")
            return None

        conn = self.get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session_id = self.generate_session_id()

        print(f"[DATABASE] Saving session: {session_id}")
        print(f"[DATABASE] Customer: {customer_info['name']}, Mobile: {customer_info['mobile']}")
        print(f"[DATABASE] Items to save: {len(cart_items)}")

        try:
            cursor.execute(
                "INSERT INTO customers (name, mobile, created_at) VALUES (?, ?, ?)",
                (customer_info["name"], customer_info["mobile"], now)
            )
            customer_id = cursor.lastrowid
            print(f"[DATABASE] Customer inserted with ID: {customer_id}")

            for i, item in enumerate(cart_items):
                cursor.execute(
                    """INSERT INTO transactions 
                       (customer_id, session_id, vegetable, weight_kg, price_per_kg, total_price, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        customer_id,
                        session_id,
                        item["vegetable"],
                        item["weight_kg"],
                        item["price_per_kg"],
                        item["total"],
                        now
                    )
                )
                print(f"[DATABASE] Item {i+1} inserted: {item['vegetable']} {item['weight_kg']}kg")

            conn.commit()
            print("[DATABASE] Commit successful.")

            cursor.execute("SELECT COUNT(*) FROM customers WHERE id = ?", (customer_id,))
            cust_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM transactions WHERE session_id = ?", (session_id,))
            txn_count = cursor.fetchone()[0]

            print(f"[DATABASE] Verification: {cust_count} customer(s), {txn_count} transaction(s)")

            grand_total = sum(item["total"] for item in cart_items)

            return {
                "customer_id": customer_id,
                "session_id": session_id,
                "items_saved": txn_count,
                "grand_total": grand_total
            }

        except Exception as e:
            conn.rollback()
            print(f"[DATABASE] ERROR: {e}")
            raise RuntimeError(f"Database save failed: {e}")

        finally:
            conn.close()

    def get_all_sessions(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                c.id, c.name, c.mobile, t.session_id,
                COUNT(t.id) as item_count,
                SUM(t.total_price) as grand_total,
                c.created_at
            FROM customers c
            JOIN transactions t ON c.id = t.customer_id
            GROUP BY c.id, t.session_id
            ORDER BY c.created_at DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        sessions = []
        for row in rows:
            sessions.append({
                "customer_id": row[0],
                "name": row[1],
                "mobile": row[2],
                "session_id": row[3],
                "item_count": row[4],
                "grand_total": row[5],
                "created_at": row[6]
            })
        return sessions

    def get_session_details(self, session_id):
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT c.name, c.mobile, c.created_at
            FROM customers c
            JOIN transactions t ON c.id = t.customer_id
            WHERE t.session_id = ?
            LIMIT 1
        """, (session_id,))

        customer_row = cursor.fetchone()
        if not customer_row:
            conn.close()
            return None

        cursor.execute("""
            SELECT vegetable, weight_kg, price_per_kg, total_price
            FROM transactions
            WHERE session_id = ?
            ORDER BY id
        """, (session_id,))

        item_rows = cursor.fetchall()
        conn.close()

        items = []
        for row in item_rows:
            items.append({
                "vegetable": row[0],
                "weight_kg": row[1],
                "price_per_kg": row[2],
                "total": row[3]
            })

        return {
            "customer": {
                "name": customer_row[0],
                "mobile": customer_row[1],
                "created_at": customer_row[2]
            },
            "session_id": session_id,
            "items": items,
            "grand_total": sum(item["total"] for item in items)
        }