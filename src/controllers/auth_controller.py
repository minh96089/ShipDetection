import functools
from typing import Callable, Optional, List
from src.config.db_config import get_connection

class UserRole:
    ADMIN = 'admin'
    USER = 'user'

class Permission:
    MANAGE_SHIPS = 'manage_ships'
    VIEW_SHIPS = 'view_ships'
    RUN_DETECTION = 'run_detection'
    VIEW_LOGS = 'view_logs'
    VIEW_STATISTICS = 'view_statistics'
    VIEW_REPORTS = 'view_reports'
    MANAGE_ZONES = 'manage_zones'
    VIEW_ALERTS = 'view_alerts'
    MANAGE_ALERTS = 'manage_alerts'
    MANAGE_USERS = 'manage_users'
ROLE_PERMISSIONS = {UserRole.ADMIN: [Permission.MANAGE_SHIPS, Permission.VIEW_SHIPS, Permission.RUN_DETECTION, Permission.VIEW_LOGS, Permission.VIEW_STATISTICS, Permission.VIEW_REPORTS, Permission.MANAGE_ZONES, Permission.VIEW_ALERTS, Permission.MANAGE_ALERTS, Permission.MANAGE_USERS], UserRole.USER: [Permission.RUN_DETECTION, Permission.VIEW_LOGS, Permission.VIEW_ALERTS]}

class CurrentUser:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.user_id = None
            cls._instance.username = None
            cls._instance.role = None
            cls._instance.full_name = None
        return cls._instance

    def set_user(self, user_id: int, username: str, role: str, full_name: str):
        self.user_id = user_id
        self.username = username
        self.role = role
        self.full_name = full_name

    def clear(self):
        self.user_id = None
        self.username = None
        self.role = None
        self.full_name = None

    def is_authenticated(self) -> bool:
        return self.user_id is not None

    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

class AuthController:

    @staticmethod
    def authenticate(username: str, password: str) -> tuple[bool, Optional[dict]]:
        try:
            conn = get_connection()
            if not conn:
                return (False, None)
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, username, full_name, role FROM users WHERE username = ? AND password = ?', (username, password))
            row = cursor.fetchone()
            conn.close()
            if row:
                user_data = {'user_id': row[0], 'username': row[1], 'full_name': row[2], 'role': row[3]}
                return (True, user_data)
            return (False, None)
        except Exception as e:
            print(f'>> Auth Error: {e}')
            return (False, None)

    @staticmethod
    def get_user(user_id: int) -> Optional[dict]:
        try:
            conn = get_connection()
            if not conn:
                return None
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, username, full_name, role FROM users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                return {'user_id': row[0], 'username': row[1], 'full_name': row[2], 'role': row[3]}
            return None
        except Exception as e:
            print(f'>> Auth Error: {e}')
            return None

    @staticmethod
    def check_permission(user_role: str, permission: str) -> bool:
        if user_role not in ROLE_PERMISSIONS:
            return False
        return permission in ROLE_PERMISSIONS[user_role]

    @staticmethod
    def has_permission(permission: str) -> bool:
        current_user = CurrentUser()
        if not current_user.is_authenticated():
            return False
        return AuthController.check_permission(current_user.role, permission)

def require_permission(permission: str):

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not AuthController.has_permission(permission):
                raise PermissionError(f"Quyền '{permission}' bị từ chối")
            return func(*args, **kwargs)
        return wrapper
    return decorator

def require_role(role: str):

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_user = CurrentUser()
            if current_user.role != role:
                raise PermissionError(f'Chỉ {role} mới có thể truy cập')
            return func(*args, **kwargs)
        return wrapper
    return decorator

def require_any_role(*roles: str):

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_user = CurrentUser()
            if current_user.role not in roles:
                raise PermissionError(f"Yêu cầu một trong các role: {', '.join(roles)}")
            return func(*args, **kwargs)
        return wrapper
    return decorator
