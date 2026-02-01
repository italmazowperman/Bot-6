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
