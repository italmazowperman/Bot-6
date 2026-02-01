import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor

class DatabaseManager:
    """Упрощенный менеджер базы данных"""
    
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        self.conn = None
        self.cursor = None
        
        if self.database_url:
            try:
                # Подключаемся к PostgreSQL
                self.conn = psycopg2.connect(self.database_url, sslmode='require')
                self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
                print("✅ Подключено к PostgreSQL")
                self._create_tables_if_not_exist()
            except Exception as e:
                print(f"❌ Ошибка подключения к PostgreSQL: {e}")
                print("⚠️  Используется временная база данных")
        else:
            print("⚠️  DATABASE_URL не установлен. Используется временная база.")
    
    def _create_tables_if_not_exist(self):
        """Создать таблицы если их нет"""
        try:
            # Создаем таблицу заказов
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    order_number VARCHAR(50) UNIQUE,
                    client_name VARCHAR(200),
                    container_count INTEGER DEFAULT 0,
                    goods_type VARCHAR(100),
                    route VARCHAR(200),
                    status VARCHAR(50),
                    departure_date TIMESTAMP,
                    arrival_iran_date TIMESTAMP,
                    truck_loading_date TIMESTAMP,
                    arrival_turkmenistan_date TIMESTAMP,
                    client_receiving_date TIMESTAMP,
                    eta_date TIMESTAMP,
                    has_loading_photo BOOLEAN DEFAULT FALSE,
                    has_local_charges BOOLEAN DEFAULT FALSE,
                    has_tex BOOLEAN DEFAULT FALSE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Создаем таблицу контейнеров
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS containers (
                    id SERIAL PRIMARY KEY,
                    order_id INTEGER REFERENCES orders(id),
                    container_number VARCHAR(50),
                    container_type VARCHAR(50),
                    weight DECIMAL(10, 2),
                    volume DECIMAL(10, 2),
                    driver_first_name VARCHAR(100),
                    driver_last_name VARCHAR(100),
                    driver_company VARCHAR(200),
                    truck_number VARCHAR(50),
                    driver_iran_phone VARCHAR(50),
                    driver_turkmenistan_phone VARCHAR(50)
                )
            """)
            
            # Создаем таблицу подписок для уведомлений
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id SERIAL PRIMARY KEY,
                    chat_id VARCHAR(100) UNIQUE,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.conn.commit()
            print("✅ Таблицы созданы или уже существуют")
            
        except Exception as e:
            print(f"❌ Ошибка при создании таблиц: {e}")
            if self.conn:
                self.conn.rollback()
    
    def get_all_orders(self) -> List[Dict]:
        """Получить все заказы"""
        if not self.cursor:
            return []
        
        try:
            self.cursor.execute("""
                SELECT * FROM orders 
                ORDER BY created_at DESC
            """)
            return self.cursor.fetchall()
        except Exception as e:
            print(f"Ошибка получения заказов: {e}")
            return []
    
    def get_order_by_number(self, order_number: str) -> Optional[Dict]:
        """Получить заказ по номеру"""
        if not self.cursor:
            return None
        
        try:
            self.cursor.execute("""
                SELECT * FROM orders 
                WHERE order_number = %s
            """, (order_number,))
            return self.cursor.fetchone()
        except Exception as e:
            print(f"Ошибка поиска заказа: {e}")
            return None
    
    def get_orders_by_status(self, status: str) -> List[Dict]:
        """Получить заказы по статусу"""
        if not self.cursor:
            return []
        
        try:
            self.cursor.execute("""
                SELECT * FROM orders 
                WHERE status = %s 
                ORDER BY created_at DESC
            """, (status,))
            return self.cursor.fetchall()
        except Exception as e:
            print(f"Ошибка получения заказов по статусу: {e}")
            return []
    
    def get_orders_by_statuses(self, statuses: List[str]) -> List[Dict]:
        """Получить заказы по нескольким статусам"""
        if not self.cursor or not statuses:
            return []
        
        try:
            placeholders = ','.join(['%s'] * len(statuses))
            query = f"""
                SELECT * FROM orders 
                WHERE status IN ({placeholders}) 
                ORDER BY created_at DESC
            """
            self.cursor.execute(query, statuses)
            return self.cursor.fetchall()
        except Exception as e:
            print(f"Ошибка получения заказов по статусам: {e}")
            return []
    
    def get_active_orders(self) -> List[Dict]:
        """Получить активные заказы"""
        active_statuses = [
            'New',
            'In Progress CHN',
            'In Transit CHN-IR',
            'In Progress IR',
            'In Transit IR-TKM'
        ]
        return self.get_orders_by_statuses(active_statuses)
    
    def search_orders(self, search_text: str) -> List[Dict]:
        """Поиск заказов"""
        if not self.cursor:
            return []
        
        try:
            search_pattern = f"%{search_text}%"
            self.cursor.execute("""
                SELECT * FROM orders 
                WHERE order_number ILIKE %s 
                   OR client_name ILIKE %s 
                   OR goods_type ILIKE %s 
                   OR route ILIKE %s
                ORDER BY created_at DESC
                LIMIT 20
            """, (search_pattern, search_pattern, search_pattern, search_pattern))
            return self.cursor.fetchall()
        except Exception as e:
            print(f"Ошибка поиска заказов: {e}")
            return []
    
    def get_statistics(self, days: int = 30) -> Dict:
        """Получить статистику"""
        if not self.cursor:
            return {
                'total_orders': 0,
                'completed_orders': 0,
                'active_orders': 0,
                'total_containers': 0,
                'total_weight': 0,
                'total_volume': 0,
                'period_days': days
            }
        
        try:
            # Общее количество заказов
            self.cursor.execute("SELECT COUNT(*) FROM orders")
            total_orders = self.cursor.fetchone()['count']
            
            # Завершенные заказы
            self.cursor.execute("""
                SELECT COUNT(*) FROM orders 
                WHERE status = 'Completed'
            """)
            completed_orders = self.cursor.fetchone()['count']
            
            # Активные заказы
            active_statuses = ['New', 'In Progress CHN', 'In Transit CHN-IR', 
                             'In Progress IR', 'In Transit IR-TKM']
            placeholders = ','.join(['%s'] * len(active_statuses))
            self.cursor.execute(f"""
                SELECT COUNT(*) FROM orders 
                WHERE status IN ({placeholders})
            """, active_statuses)
            active_orders = self.cursor.fetchone()['count']
            
            # Контейнеры
            self.cursor.execute("""
                SELECT 
                    COUNT(*) as container_count,
                    COALESCE(SUM(weight), 0) as total_weight,
                    COALESCE(SUM(volume), 0) as total_volume
                FROM containers
            """)
            container_stats = self.cursor.fetchone()
            
            return {
                'total_orders': total_orders or 0,
                'completed_orders': completed_orders or 0,
                'active_orders': active_orders or 0,
                'total_containers': container_stats['container_count'] or 0,
                'total_weight': float(container_stats['total_weight'] or 0),
                'total_volume': float(container_stats['total_volume'] or 0),
                'period_days': days
            }
            
        except Exception as e:
            print(f"Ошибка получения статистики: {e}")
            return {}
    
    def close(self):
        """Закрыть соединения"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
        except:
            pass

# В класс DatabaseManager добавьте методы:

def get_orders_without_photos(self) -> List[Dict]:
    """Получить заказы без фото загрузки"""
    if not self.cursor:
        return []
    
    try:
        self.cursor.execute("""
            SELECT * FROM orders 
            WHERE has_loading_photo = FALSE 
            AND status NOT IN ('Completed', 'Cancelled')
            ORDER BY creation_date DESC
        """)
        return self.cursor.fetchall()
    except Exception as e:
        print(f"Ошибка получения заказов без фото: {e}")
        return []

def get_orders_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict]:
    """Получить заказы за период"""
    if not self.cursor:
        return []
    
    try:
        self.cursor.execute("""
            SELECT * FROM orders 
            WHERE creation_date BETWEEN %s AND %s
            ORDER BY creation_date DESC
        """, (start_date, end_date))
        return self.cursor.fetchall()
    except Exception as e:
        print(f"Ошибка получения заказов за период: {e}")
        return []

def get_orders_with_events_today(self) -> List[Dict]:
    """Получить заказы с событиями сегодня"""
    if not self.cursor:
        return []
    
    try:
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        
        self.cursor.execute("""
            SELECT * FROM orders 
            WHERE (departure_date::date = %s OR
                   arrival_iran_date::date = %s OR
                   truck_loading_date::date = %s OR
                   arrival_turkmenistan_date::date = %s OR
                   client_receiving_date::date = %s OR
                   eta_date::date = %s)
            ORDER BY creation_date DESC
        """, (today, today, today, today, today, today))
        return self.cursor.fetchall()
    except Exception as e:
        print(f"Ошибка получения событий сегодня: {e}")
        return []

def get_upcoming_events(self, from_date: datetime, to_date: datetime) -> List[Dict]:
    """Получить предстоящие события"""
    if not self.cursor:
        return []
    
    try:
        self.cursor.execute("""
            SELECT 
                order_number,
                'Отплытие из Китая' as event_type,
                departure_date as event_date
            FROM orders 
            WHERE departure_date BETWEEN %s AND %s
            
            UNION ALL
            
            SELECT 
                order_number,
                'Прибытие в Иран' as event_type,
                arrival_iran_date as event_date
            FROM orders 
            WHERE arrival_iran_date BETWEEN %s AND %s
            
            UNION ALL
            
            SELECT 
                order_number,
                'Погрузка на грузовик' as event_type,
                truck_loading_date as event_date
            FROM orders 
            WHERE truck_loading_date BETWEEN %s AND %s
            
            UNION ALL
            
            SELECT 
                order_number,
                'Прибытие в Туркменистан' as event_type,
                arrival_turkmenistan_date as event_date
            FROM orders 
            WHERE arrival_turkmenistan_date BETWEEN %s AND %s
            
            UNION ALL
            
            SELECT 
                order_number,
                'Получение клиентом' as event_type,
                client_receiving_date as event_date
            FROM orders 
            WHERE client_receiving_date BETWEEN %s AND %s
            
            ORDER BY event_date
        """, (from_date, to_date, from_date, to_date, from_date, to_date, 
              from_date, to_date, from_date, to_date))
        
        return self.cursor.fetchall()
    except Exception as e:
        print(f"Ошибка получения предстоящих событий: {e}")
        return []
