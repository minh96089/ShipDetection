import os
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

def bootstrap_paths():
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).resolve().parent
        meipass = Path(getattr(sys, '_MEIPASS', exe_dir))
        for path in (meipass, exe_dir):
            s = str(path)
            if s not in sys.path:
                sys.path.insert(0, s)
        return exe_dir
    root = Path(__file__).resolve().parent.parent
    s = str(root)
    if s not in sys.path:
        sys.path.insert(0, s)
    return root

def fix_torch_dll(project_root):
    if getattr(sys, 'frozen', False):
        torch_lib_path = Path(getattr(sys, '_MEIPASS', project_root)) / 'torch' / 'lib'
    else:
        torch_lib_path = project_root / 'venv' / 'Lib' / 'site-packages' / 'torch' / 'lib'
    if torch_lib_path.exists():
        os.add_dll_directory(str(torch_lib_path))
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
    os.environ.setdefault('PADDLE_SKIP_CHECK', '1')

project_root = bootstrap_paths()
fix_torch_dll(project_root)
from src.controllers.main_controller import MainController
from src.views.login_view import LoginView
from src.config.db_config import get_connection
from src.controllers.auth_controller import AuthController, CurrentUser

def start_main_app(username, password, login_view, login_root):
    success, user_data = AuthController.authenticate(username, password)
    if not success:
        messagebox.showerror('Đăng nhập thất bại', 'Tên đăng nhập hoặc mật khẩu không chính xác!', parent=login_view)
        return
    try:
        current_user = CurrentUser()
        current_user.set_user(user_id=user_data['user_id'], username=user_data['username'], role=user_data['role'], full_name=user_data['full_name'])
        print(f">> Đăng nhập thành công với tài khoản: {username} (Role: {user_data['role']})")
        login_view.destroy()
        login_root.destroy()
        print('>> Đang khởi động giao diện giám sát...')
        main_controller = MainController()
        # Gán callback để quay về login khi đăng xuất
        main_controller._on_logout_to_login = launch_login
        main_controller.run()
    except Exception as e:
        messagebox.showerror('Lỗi', f'Lỗi khi khởi động: {str(e)}')

def launch_login():
    """Mở màn hình đăng nhập (dùng cho cả lần đầu và sau khi đăng xuất)."""
    login_root = tk.Tk()
    login_root.withdraw()
    login_view = LoginView(login_root)
    login_view.on_login_success = lambda u, p: start_main_app(u, p, login_view, login_root)
    login_view.protocol('WM_DELETE_WINDOW', lambda: (login_view.destroy(), login_root.destroy()))
    login_root.mainloop()

if __name__ == '__main__':
    try:
        print('>> Đang khởi động Hệ thống Ship Detection...')
        launch_login()
    except Exception as e:
        print(f'Có lỗi xảy ra khi khởi động: {e}')
        import traceback
        traceback.print_exc()
        input('Nhấn Enter để thoát...')
