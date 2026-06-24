import psycopg2
import psycopg2.extras
import time


class Database:
    def __init__(self, db_url):
        self.db_url = db_url
        self.conn = self._connect()
        self.create_tables()

    def _connect(self):
        return psycopg2.connect(self.db_url, sslmode='require')

    def _cursor(self):
        try:
            self.conn.isolation_level
        except Exception:
            self.conn = self._connect()
        try:
            self.conn.cursor().execute("SELECT 1")
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            self.conn = self._connect()
        return self.conn.cursor()

    def create_tables(self):
        try:
            with self._cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sasha_users (
                        id BIGINT PRIMARY KEY,
                        name TEXT,
                        coins INTEGER DEFAULT 100,
                        messages INTEGER DEFAULT 0,
                        last_card_time DOUBLE PRECISION DEFAULT 0,
                        last_gift_time DOUBLE PRECISION DEFAULT 0,
                        gift_streak INTEGER DEFAULT 0,
                        last_streak_day TEXT DEFAULT ''
                    )
                """)
                for col, typedef in [
                    ("last_gift_time", "DOUBLE PRECISION DEFAULT 0"),
                    ("gift_streak", "INTEGER DEFAULT 0"),
                    ("last_streak_day", "TEXT DEFAULT ''"),
                ]:
                    cursor.execute(
                        f"ALTER TABLE sasha_users ADD COLUMN IF NOT EXISTS {col} {typedef}"
                    )
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sasha_collection (
                        owner_id BIGINT,
                        card_id BIGINT,
                        rarity TEXT,
                        FOREIGN KEY (owner_id) REFERENCES sasha_users(id) ON DELETE CASCADE
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sasha_achievements (
                        user_id BIGINT,
                        achievement_text TEXT,
                        date_earned TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES sasha_users(id) ON DELETE CASCADE
                    )
                """)
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"DB Error (create_tables): {e}")

    # ----------------------------------------------------------------
    # СТРІК
    # ----------------------------------------------------------------
    def get_streak_data(self, user_id):
        try:
            with self._cursor() as cursor:
                cursor.execute("SELECT gift_streak, last_streak_day FROM sasha_users WHERE id = %s", (user_id,))
                res = cursor.fetchone()
                return (res[0] or 0, res[1] or "") if res else (0, "")
        except Exception:
            self.conn.rollback()
            return (0, "")

    def update_streak(self, user_id, streak, day_str):
        try:
            with self._cursor() as cursor:
                cursor.execute(
                    "UPDATE sasha_users SET gift_streak = %s, last_streak_day = %s WHERE id = %s",
                    (streak, day_str, user_id)
                )
                self.conn.commit()
        except Exception:
            self.conn.rollback()

    # ----------------------------------------------------------------
    # ТОПИ
    # ----------------------------------------------------------------
    def get_leaderboard(self):
        try:
            with self._cursor() as cursor:
                cursor.execute("SELECT name, coins FROM sasha_users ORDER BY coins DESC LIMIT 10")
                return cursor.fetchall()
        except Exception:
            self.conn.rollback()
            return []

    def get_user_rank(self, user_id):
        try:
            with self._cursor() as cursor:
                cursor.execute("""
                    SELECT position FROM (
                        SELECT id, ROW_NUMBER() OVER (ORDER BY coins DESC) as position
                        FROM sasha_users
                    ) sub WHERE id = %s
                """, (user_id,))
                res = cursor.fetchone()
                return res[0] if res else "—"
        except Exception:
            self.conn.rollback()
            return "—"

    def get_user_at_rank(self, place: int):
        try:
            with self._cursor() as cursor:
                cursor.execute("""
                    SELECT name, coins FROM (
                        SELECT name, coins, ROW_NUMBER() OVER (ORDER BY coins DESC) as position
                        FROM sasha_users
                    ) sub WHERE position = %s
                """, (place,))
                return cursor.fetchone()
        except Exception:
            self.conn.rollback()
            return None

    def get_total_players(self):
        try:
            with self._cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM sasha_users")
                res = cursor.fetchone()
                return res[0] if res else 0
        except Exception:
            self.conn.rollback()
            return 0

    # ----------------------------------------------------------------
    # КОРИСТУВАЧІ
    # ----------------------------------------------------------------
    def update_user(self, user_id, name):
        try:
            with self._cursor() as cursor:
                cursor.execute("""
                    INSERT INTO sasha_users (id, name, coins) VALUES (%s, %s, 100)
                    ON CONFLICT (id) DO NOTHING
                """, (user_id, name))
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"Error in update_user: {e}")

    def set_user_name(self, user_id, name):
        try:
            with self._cursor() as cursor:
                cursor.execute("UPDATE sasha_users SET name = %s WHERE id = %s", (name, user_id))
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"Error in set_user_name: {e}")

    def update_message_count(self, user_id):
        try:
            with self._cursor() as cursor:
                cursor.execute("UPDATE sasha_users SET messages = messages + 1 WHERE id = %s", (user_id,))
                self.conn.commit()
        except Exception:
            self.conn.rollback()

    def get_user_data(self, user_id):
        try:
            with self._cursor() as cursor:
                cursor.execute("SELECT coins, messages FROM sasha_users WHERE id = %s", (user_id,))
                res = cursor.fetchone()
                return res if res else (0, 0)
        except Exception:
            self.conn.rollback()
            return (0, 0)

    def get_user_name(self, user_id):
        try:
            with self._cursor() as cursor:
                cursor.execute("SELECT name FROM sasha_users WHERE id = %s", (user_id,))
                res = cursor.fetchone()
                return res[0] if res else None
        except Exception:
            self.conn.rollback()
            return None

    def add_coins(self, user_id, amount):
        try:
            with self._cursor() as cursor:
                cursor.execute("UPDATE sasha_users SET coins = coins + %s WHERE id = %s", (amount, user_id))
                self.conn.commit()
        except Exception:
            self.conn.rollback()

    def reset_coins(self, user_id):
        try:
            with self._cursor() as cursor:
                cursor.execute("UPDATE sasha_users SET coins = 0 WHERE id = %s", (user_id,))
                self.conn.commit()
        except Exception:
            self.conn.rollback()

    def get_all_users(self):
        try:
            with self._cursor() as cursor:
                cursor.execute("SELECT id, name FROM sasha_users")
                return cursor.fetchall()
        except Exception:
            self.conn.rollback()
            return []

    def get_all_users_paged(self, page: int, per_page: int):
        try:
            offset = (page - 1) * per_page
            with self._cursor() as cursor:
                cursor.execute(
                    "SELECT id, name, coins FROM sasha_users ORDER BY coins DESC LIMIT %s OFFSET %s",
                    (per_page, offset)
                )
                return cursor.fetchall()
        except Exception:
            self.conn.rollback()
            return []

    # ----------------------------------------------------------------
    # КОЛЕКЦІЯ
    # ----------------------------------------------------------------
    def add_to_collection(self, owner_id, card_id, rarity):
        try:
            with self._cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM sasha_collection WHERE owner_id = %s AND card_id = %s",
                    (owner_id, card_id)
                )
                if cursor.fetchone():
                    return False
                cursor.execute(
                    "INSERT INTO sasha_collection (owner_id, card_id, rarity) VALUES (%s, %s, %s)",
                    (owner_id, card_id, rarity)
                )
                self.conn.commit()
                return True
        except Exception:
            self.conn.rollback()
            return False

    def get_total_collected(self, user_id):
        try:
            with self._cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM sasha_collection WHERE owner_id = %s", (user_id,))
                res = cursor.fetchone()
                return res[0] if res else 0
        except Exception:
            self.conn.rollback()
            return 0

    # ----------------------------------------------------------------
    # КАРТКИ / ЧАС
    # ----------------------------------------------------------------
    def get_last_card_time(self, user_id):
        try:
            with self._cursor() as cursor:
                cursor.execute("SELECT last_card_time FROM sasha_users WHERE id = %s", (user_id,))
                res = cursor.fetchone()
                return res[0] if res else 0
        except Exception:
            self.conn.rollback()
            return 0

    def set_last_card_time(self, user_id, timestamp):
        try:
            with self._cursor() as cursor:
                cursor.execute(
                    "UPDATE sasha_users SET last_card_time = %s WHERE id = %s",
                    (timestamp, user_id)
                )
                self.conn.commit()
        except Exception:
            self.conn.rollback()

    def get_last_gift_time(self, user_id):
        try:
            with self._cursor() as cursor:
                cursor.execute("SELECT last_gift_time FROM sasha_users WHERE id = %s", (user_id,))
                res = cursor.fetchone()
                return res[0] if res else 0
        except Exception:
            self.conn.rollback()
            return 0

    def set_last_gift_time(self, user_id, timestamp):
        try:
            with self._cursor() as cursor:
                cursor.execute(
                    "UPDATE sasha_users SET last_gift_time = %s WHERE id = %s",
                    (timestamp, user_id)
                )
                self.conn.commit()
        except Exception:
            self.conn.rollback()

    def get_random_user(self):
        try:
            with self._cursor() as cursor:
                cursor.execute("SELECT id, name FROM sasha_users ORDER BY RANDOM() LIMIT 1")
                return cursor.fetchone()
        except Exception:
            self.conn.rollback()
            return None

    # ----------------------------------------------------------------
    # НАГОРОДИ
    # ----------------------------------------------------------------
    def add_achievement(self, user_id, text):
        try:
            with self._cursor() as cursor:
                cursor.execute(
                    "INSERT INTO sasha_achievements (user_id, achievement_text) VALUES (%s, %s)",
                    (user_id, text)
                )
                self.conn.commit()
                return True
        except Exception:
            self.conn.rollback()
            return False

    def get_user_achievements(self, user_id):
        try:
            with self._cursor() as cursor:
                cursor.execute(
                    "SELECT achievement_text FROM sasha_achievements WHERE user_id = %s ORDER BY date_earned ASC",
                    (user_id,)
                )
                return [row[0] for row in cursor.fetchall()]
        except Exception:
            self.conn.rollback()
            return []

    def remove_achievement(self, user_id, index: int):
        try:
            with self._cursor() as cursor:
                cursor.execute("""
                    SELECT ctid FROM sasha_achievements
                    WHERE user_id = %s
                    ORDER BY date_earned ASC
                    OFFSET %s LIMIT 1
                """, (user_id, index))
                row = cursor.fetchone()
                if row:
                    cursor.execute("DELETE FROM sasha_achievements WHERE ctid = %s", (row[0],))
                    self.conn.commit()
                    return True
                return False
        except Exception:
            self.conn.rollback()
            return False

    # ----------------------------------------------------------------
    # ЛОТЕРЕЯ
    # ----------------------------------------------------------------
    def get_lottery_tickets(self, user_id):
        try:
            with self._cursor() as cursor:
                cursor.execute("SELECT lottery_tickets FROM sasha_users WHERE id = %s", (user_id,))
                res = cursor.fetchone()
                return res[0] if res else 0
        except Exception:
            self.conn.rollback()
            return 0

    def add_lottery_ticket(self, user_id):
        try:
            with self._cursor() as cursor:
                cursor.execute(
                    "UPDATE sasha_users SET lottery_tickets = COALESCE(lottery_tickets, 0) + 1 WHERE id = %s",
                    (user_id,)
                )
                self.conn.commit()
        except Exception:
            self.conn.rollback()

    def use_lottery_ticket(self, user_id):
        try:
            with self._cursor() as cursor:
                cursor.execute(
                    "UPDATE sasha_users SET lottery_tickets = lottery_tickets - 1 WHERE id = %s",
                    (user_id,)
                )
                self.conn.commit()
        except Exception:
            self.conn.rollback()

    def _ensure_lottery_column(self):
        try:
            with self._cursor() as cursor:
                cursor.execute(
                    "ALTER TABLE sasha_users ADD COLUMN IF NOT EXISTS lottery_tickets INTEGER DEFAULT 0"
                )
                self.conn.commit()
        except Exception:
            self.conn.rollback()
