"""
MES Production System - Role Service
Централизованный сервис для управления ролями и правами доступа.
"""
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any


class RoleService:
    """
    Сервис для управления ролями с поддержкой:
    - Создания/удаления/клонирования ролей
    - Управления правами
    - Аудита изменений
    - Проверки зависимостей
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def get_connection(self) -> sqlite3.Connection:
        """Получить соединение с БД с настройкой row_factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # ==================== Роли ====================
    
    def create_role(self, name: str, label: str, description: str = None,
                    parent_role: str = None, created_by: int = None,
                    is_builtin: bool = False) -> Tuple[bool, str, Optional[dict]]:
        """
        Создание новой роли.
        
        Returns:
            (success: bool, message: str, role_data: dict or None)
        """
        if not name or not isinstance(name, str):
            return False, "Имя роли обязательно", None
        
        if not name.replace('_', '').isalnum():
            return False, "Имя роли должно содержать только буквы, цифры и подчёркивания", None
        
        if not label:
            return False, "Название роли обязательно", None
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Проверка существования роли
            cursor.execute('SELECT 1 FROM role_permissions WHERE role = ? LIMIT 1', (name,))
            if cursor.fetchone():
                return False, f"Роль '{name}' уже существует", None
            
            # Если указан родитель, проверить его существование
            if parent_role:
                cursor.execute('SELECT 1 FROM role_permissions WHERE role = ? LIMIT 1', (parent_role,))
                if not cursor.fetchone():
                    return False, f"Родительская роль '{parent_role}' не найдена", None
            
            # Создание роли (маркерная запись с пустым permission)
            cursor.execute(
                'INSERT INTO role_permissions (role, permission) VALUES (?, ?)',
                (name, '')
            )
            
            # Если есть родитель, скопировать его права
            if parent_role:
                cursor.execute(
                    'SELECT permission FROM role_permissions WHERE role = ? AND permission != ?',
                    (parent_role, '')
                )
                parent_perms = [r['permission'] for r in cursor.fetchall()]
                for perm in parent_perms:
                    cursor.execute(
                        'INSERT INTO role_permissions (role, permission) VALUES (?, ?)',
                        (name, perm)
                    )
            
            conn.commit()
            
            # Логирование аудита
            self._log_audit(
                role_name=name,
                action='created',
                new_value={'name': name, 'label': label, 'description': description, 
                          'parent_role': parent_role},
                changed_by=created_by
            )
            
            return True, f"Роль '{name}' создана", {'name': name, 'label': label}
            
        except Exception as e:
            conn.rollback()
            return False, f"Ошибка создания роли: {str(e)}", None
        finally:
            conn.close()
    
    def clone_role(self, source_role: str, new_name: str, new_label: str,
                   created_by: int = None) -> Tuple[bool, str, Optional[dict]]:
        """
        Клонирование существующей роли.
        """
        if not source_role or not new_name:
            return False, "Исходная роль и новое имя обязательны", None
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Проверка существования исходной роли
            cursor.execute(
                'SELECT permission FROM role_permissions WHERE role = ?',
                (source_role,)
            )
            source_perms = [r['permission'] for r in cursor.fetchall()]
            
            if not source_perms:
                return False, f"Роль '{source_role}' не найдена или не имеет прав", None
            
            # Создание новой роли с теми же правами
            success, msg, _ = self.create_role(
                name=new_name,
                label=new_label,
                description=f"Клонировано из роли '{source_role}'",
                created_by=created_by
            )
            
            if not success:
                return False, msg, None
            
            # Копирование прав
            for perm in source_perms:
                if perm:  # Пропустить маркерную запись
                    cursor.execute(
                        'INSERT INTO role_permissions (role, permission) VALUES (?, ?)',
                        (new_name, perm)
                    )
            
            conn.commit()
            
            # Логирование аудита
            self._log_audit(
                role_name=new_name,
                action='cloned',
                new_value={'source_role': source_role, 'permissions': source_perms},
                changed_by=created_by
            )
            
            return True, f"Роль '{new_name}' создана как клон '{source_role}'", {'name': new_name}
            
        except Exception as e:
            conn.rollback()
            return False, f"Ошибка клонирования: {str(e)}", None
        finally:
            conn.close()
    
    def delete_role(self, role_name: str, force: bool = False, 
                    deleted_by: int = None) -> Tuple[bool, str, Optional[dict]]:
        """
        Удаление роли с проверкой зависимостей.
        """
        builtin_roles = ['admin', 'operator', 'viewer']
        
        if role_name in builtin_roles:
            return False, "Нельзя удалить встроенную роль", None
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Проверка существования роли
            cursor.execute('SELECT 1 FROM role_permissions WHERE role = ? LIMIT 1', (role_name,))
            if not cursor.fetchone():
                return False, f"Роль '{role_name}' не найдена", None
            
            # Проверка зависимостей - пользователи с этой ролью
            cursor.execute('SELECT COUNT(*) as cnt FROM users WHERE role = ?', (role_name,))
            users_count = cursor.fetchone()['cnt']
            
            if users_count > 0 and not force:
                return False, (f"Нельзя удалить роль: её имеют {users_count} пользователей. "
                              f"Переназначьте пользователей или используйте force=True"), None
            
            # Получить права перед удалением (для аудита)
            cursor.execute(
                'SELECT permission FROM role_permissions WHERE role = ? AND permission != ?',
                (role_name, '')
            )
            deleted_perms = [r['permission'] for r in cursor.fetchall()]
            
            # Удаление всех записей роли
            cursor.execute('DELETE FROM role_permissions WHERE role = ?', (role_name,))
            
            conn.commit()
            
            # Логирование аудита
            self._log_audit(
                role_name=role_name,
                action='deleted',
                old_value={'permissions': deleted_perms, 'users_affected': users_count},
                changed_by=deleted_by
            )
            
            return True, f"Роль '{role_name}' удалена", {'users_affected': users_count}
            
        except Exception as e:
            conn.rollback()
            return False, f"Ошибка удаления: {str(e)}", None
        finally:
            conn.close()
    
    def get_role_dependencies(self, role_name: str) -> Tuple[bool, str, Optional[dict]]:
        """
        Получить информацию о зависимостях роли.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Проверка существования роли
            cursor.execute('SELECT 1 FROM role_permissions WHERE role = ? LIMIT 1', (role_name,))
            if not cursor.fetchone():
                return False, f"Роль '{role_name}' не найдена", None
            
            # Пользователи с этой ролью
            cursor.execute('''
                SELECT id, username, role 
                FROM users 
                WHERE role = ? 
                ORDER BY username
            ''', (role_name,))
            users = [{'id': r['id'], 'username': r['username']} for r in cursor.fetchall()]
            
            # Количество прав
            cursor.execute(
                'SELECT COUNT(*) as cnt FROM role_permissions WHERE role = ? AND permission != ?',
                (role_name, '')
            )
            permissions_count = cursor.fetchone()['cnt']
            
            return True, "OK", {
                'users_count': len(users),
                'users': users,
                'permissions_count': permissions_count,
                'is_builtin': role_name in ['admin', 'operator', 'viewer']
            }
            
        except Exception as e:
            return False, f"Ошибка: {str(e)}", None
        finally:
            conn.close()
    
    # ==================== Права ====================
    
    def get_role_permissions(self, role_name: str) -> Tuple[bool, str, List[str]]:
        """Получить список прав роли."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT permission FROM role_permissions WHERE role = ? AND permission != ?',
                (role_name, '')
            )
            perms = [r['permission'] for r in cursor.fetchall()]
            return True, "OK", perms
        except Exception as e:
            return False, f"Ошибка: {str(e)}", []
        finally:
            conn.close()
    
    def set_role_permissions(self, role_name: str, permissions: List[str],
                            changed_by: int = None) -> Tuple[bool, str]:
        """
        Установить права для роли (полная замена).
        """
        from utils.permissions import PERMISSIONS
        
        # Валидация прав
        invalid = [p for p in permissions if p not in PERMISSIONS]
        if invalid:
            return False, f"Недопустимые права: {', '.join(invalid)}"
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Получить старые права для аудита
            cursor.execute(
                'SELECT permission FROM role_permissions WHERE role = ? AND permission != ?',
                (role_name, '')
            )
            old_perms = [r['permission'] for r in cursor.fetchall()]
            
            # Удаление старых прав
            cursor.execute('DELETE FROM role_permissions WHERE role = ?', (role_name,))
            
            # Вставка новых прав
            for perm in permissions:
                cursor.execute(
                    'INSERT INTO role_permissions (role, permission) VALUES (?, ?)',
                    (role_name, perm)
                )
            
            conn.commit()
            
            # Логирование аудита
            self._log_audit(
                role_name=role_name,
                action='permissions_updated',
                old_value={'permissions': old_perms},
                new_value={'permissions': permissions},
                changed_by=changed_by
            )
            
            return True, "Права обновлены"
            
        except Exception as e:
            conn.rollback()
            return False, f"Ошибка обновления прав: {str(e)}"
        finally:
            conn.close()
    
    def add_role_permissions(self, role_name: str, permissions: List[str],
                            changed_by: int = None) -> Tuple[bool, str]:
        """Добавить права к существующим."""
        from utils.permissions import PERMISSIONS
        
        invalid = [p for p in permissions if p not in PERMISSIONS]
        if invalid:
            return False, f"Недопустимые права: {', '.join(invalid)}"
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Получить текущие права
            cursor.execute(
                'SELECT permission FROM role_permissions WHERE role = ? AND permission != ?',
                (role_name, '')
            )
            current_perms = set(r['permission'] for r in cursor.fetchall())
            
            # Добавить новые
            added = []
            for perm in permissions:
                if perm not in current_perms:
                    cursor.execute(
                        'INSERT INTO role_permissions (role, permission) VALUES (?, ?)',
                        (role_name, perm)
                    )
                    added.append(perm)
            
            conn.commit()
            
            if added:
                self._log_audit(
                    role_name=role_name,
                    action='permissions_added',
                    new_value={'added_permissions': added},
                    changed_by=changed_by
                )
            
            return True, f"Добавлено {len(added)} прав"
            
        except Exception as e:
            conn.rollback()
            return False, f"Ошибка: {str(e)}"
        finally:
            conn.close()
    
    # ==================== Аудит ====================
    
    def _log_audit(self, role_name: str, action: str, 
                   old_value: dict = None, new_value: dict = None,
                   changed_by: int = None, ip_address: str = None):
        """Внутренний метод для логирования аудита."""
        # Таблица аудита может ещё не существовать - это нормально
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Проверка существования таблицы аудита
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='role_audit_log'"
            )
            if not cursor.fetchone():
                # Таблицы нет - просто возвращаемся без ошибки
                return
            
            cursor.execute('''
                INSERT INTO role_audit_log 
                (role_id, action, old_value, new_value, changed_by, changed_at, ip_address)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                role_name,  # Используем имя роли вместо ID для совместимости
                action,
                json.dumps(old_value) if old_value else None,
                json.dumps(new_value) if new_value else None,
                changed_by,
                datetime.now().isoformat(),
                ip_address
            ))
            conn.commit()
        except Exception:
            # Игнорируем ошибки аудита - они не должны ломать основную функциональность
            pass
        finally:
            conn.close()
    
    def get_audit_log(self, role_name: str = None, limit: int = 50) -> Tuple[bool, str, List[dict]]:
        """Получить журнал аудита."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Проверка существования таблицы
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='role_audit_log'"
            )
            if not cursor.fetchone():
                return False, "Таблица аудита ещё не создана", []
            
            if role_name:
                cursor.execute('''
                    SELECT * FROM role_audit_log 
                    WHERE role_id = ?
                    ORDER BY changed_at DESC
                    LIMIT ?
                ''', (role_name, limit))
            else:
                cursor.execute('''
                    SELECT * FROM role_audit_log 
                    ORDER BY changed_at DESC
                    LIMIT ?
                ''', (limit,))
            
            rows = cursor.fetchall()
            logs = [dict(r) for r in rows]
            
            return True, "OK", logs
            
        except Exception as e:
            return False, f"Ошибка: {str(e)}", []
        finally:
            conn.close()
    
    # ==================== Утилиты ====================
    
    def get_all_roles(self) -> List[dict]:
        """Получить список всех ролей."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT role FROM role_permissions ORDER BY role')
            roles = [r['role'] for r in cursor.fetchall()]
            
            # Разделить на встроенные и кастомные
            builtin = ['admin', 'operator', 'viewer']
            result = []
            for role in roles:
                result.append({
                    'name': role,
                    'is_builtin': role in builtin,
                    'label': role.capitalize() if role not in builtin else {
                        'admin': 'Администратор',
                        'operator': 'Оператор',
                        'viewer': 'Наблюдатель'
                    }.get(role, role)
                })
            return result
        finally:
            conn.close()
    
    def reset_to_defaults(self, role_name: str, changed_by: int = None) -> Tuple[bool, str]:
        """Сбросить права роли к значениям по умолчанию."""
        from utils.permissions import DEFAULT_ROLE_PERMISSIONS
        
        if role_name not in DEFAULT_ROLE_PERMISSIONS:
            return False, f"Нет прав по умолчанию для роли '{role_name}'"
        
        default_perms = DEFAULT_ROLE_PERMISSIONS[role_name]
        return self.set_role_permissions(role_name, default_perms, changed_by)
