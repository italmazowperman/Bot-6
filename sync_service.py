import os
import requests
from datetime import datetime
from typing import Dict, List, Optional

class SyncService:
    """Сервис синхронизации с WPF программой"""
    
    def __init__(self):
        self.api_key = os.getenv('SYNC_API_KEY')
        self.sync_endpoint = os.getenv('SYNC_ENDPOINT')
        self.last_sync_time = None
    
    def is_configured(self) -> bool:
        """Проверка настроек синхронизации"""
        return bool(self.api_key and self.sync_endpoint)
    
    def sync_orders_from_wpf(self) -> List[Dict]:
        """Синхронизировать заказы из WPF программы"""
        if not self.is_configured():
            print("⚠️  Синхронизация не настроена. Установите SYNC_API_KEY и SYNC_ENDPOINT")
            return []
        
        try:
            # Здесь будет API вызов к вашей WPF программе
            # Предполагаем, что WPF программа отдает данные в формате JSON
            response = requests.post(
                self.sync_endpoint,
                headers={'Authorization': f'Bearer {self.api_key}'},
                json={'action': 'get_orders'}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.last_sync_time = datetime.now()
                print(f"✅ Синхронизация успешна. Получено {len(data.get('orders', []))} заказов")
                return data.get('orders', [])
            else:
                print(f"❌ Ошибка синхронизации: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Ошибка при синхронизации: {e}")
            return []
    
    def send_notification_to_wpf(self, order_data: Dict, notification_type: str) -> bool:
        """Отправить уведомление в WPF программу"""
        if not self.is_configured():
            return False
        
        try:
            response = requests.post(
                self.sync_endpoint,
                headers={'Authorization': f'Bearer {self.api_key}'},
                json={
                    'action': 'notification',
                    'type': notification_type,
                    'order': order_data,
                    'timestamp': datetime.now().isoformat()
                }
            )
            return response.status_code == 200
        except:
            return False
    
    def get_sync_status(self) -> Dict:
        """Получить статус синхронизации"""
        return {
            'configured': self.is_configured(),
            'last_sync': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'api_key_set': bool(self.api_key),
            'endpoint_set': bool(self.sync_endpoint)
        }
