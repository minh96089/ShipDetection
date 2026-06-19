import os
import shutil
import time
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from src.config.db_config import get_connection
from src.views.add_ship_view import AddShipView
from src.views.edit_ship_view import EditShipView
from src.controllers.auth_controller import AuthController, Permission

class ShipController:

    def __init__(self, view, root, class_options):
        self.view = view
        self.root = root
        self.class_options = class_options
        self.view.refresh_button.config(command=self.refresh_ship_list)
        self.view.add_ship_btn.config(command=self.open_add_ship_dialog)
        self.view.ship_tree.bind('<<TreeviewSelect>>', self.on_ship_selected)
        self.view.ship_tree.bind('<ButtonRelease-1>', self.on_tree_clicked)
        from src.utils.path_utils import get_external_root
        self.project_root = get_external_root()
        self.profile_images_dir = self.project_root / 'outputs' / 'ship_profiles'
        os.makedirs(self.profile_images_dir, exist_ok=True)
        self.refresh_ship_list()

    def get_db_connection(self):
        return get_connection()

    def refresh_ship_list(self, event=None):
        try:
            conn = self.get_db_connection()
            if not conn:
                self.view.ship_refresh_status.config(text='Lỗi kết nối', fg='red')
                return
            cursor = conn.cursor()
            cursor.execute('\n                SELECT ship_id, so_hieu, loai_tau, mo_ta, anh_dai_dien, thoi_gian_tao\n                FROM ship\n                ORDER BY thoi_gian_tao DESC\n            ')
            rows = cursor.fetchall()
            formatted_rows = []
            for r in rows:
                dt_str = r.thoi_gian_tao.strftime('%Y-%m-%d %H:%M:%S') if r.thoi_gian_tao else ''
                formatted_rows.append((r.ship_id, r.so_hieu, r.loai_tau, r.mo_ta, r.anh_dai_dien, dt_str))
            self.view.refresh_ship_list_ui(formatted_rows)
            self.view.ship_refresh_status.config(text='Đã cập nhật', fg='green')
            conn.close()
        except Exception as e:
            self.view.ship_refresh_status.config(text=f'Lỗi: {e}', fg='red')
            print(f'Lỗi lấy danh sách tàu: {e}')

    def on_ship_selected(self, event):
        selection = self.view.ship_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        values = self.view.ship_tree.item(item_id, 'values')
        if not values:
            return
        so_hieu = values[0]
        class_name = values[1]
        anh_path = self.view.ship_img_paths.get(item_id, '')
        if anh_path and (not os.path.isabs(anh_path)):
            anh_path = os.path.join(self.project_root, anh_path)
        mo_ta = 'Không có mô tả'
        try:
            conn = self.get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('SELECT mo_ta FROM ship WHERE so_hieu=?', (so_hieu,))
                row = cursor.fetchone()
                if row and row.mo_ta:
                    mo_ta = row.mo_ta
                conn.close()
        except Exception:
            pass
        info = f'🚢 Tàu: {class_name}\n🔢 Số hiệu: {so_hieu}\n📝 Mô tả: {mo_ta}'
        self.view.show_ship_info(info, anh_path)
        self.load_ship_history(so_hieu)

    def on_tree_clicked(self, event):
        region = self.view.ship_tree.identify_region(event.x, event.y)
        if region != 'cell':
            return
        column = self.view.ship_tree.identify_column(event.x)
        item_id = self.view.ship_tree.identify_row(event.y)
        if not item_id:
            return
        self.view.ship_tree.selection_set(item_id)
        self.on_ship_selected(None)
        if column == '#4' and AuthController.has_permission(Permission.MANAGE_SHIPS):
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label='✏️ Sửa thông tin tàu', command=self.open_edit_ship_dialog)
            menu.add_command(label='🗑️ Xóa tàu', command=self.delete_ship)
            x_root = event.x_root
            y_root = event.y_root
            menu.post(x_root, y_root)

    def delete_ship(self):
        if not AuthController.has_permission(Permission.MANAGE_SHIPS):
            messagebox.showerror('Quyền hạn chế', 'Bạn không có quyền xóa tàu. Liên hệ quản trị viên.', parent=self.root)
            return
        selection = self.view.ship_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        values = self.view.ship_tree.item(item_id, 'values')
        so_hieu = values[0]
        class_name = values[1]
        if messagebox.askyesno('Xác nhận', f'Bạn có chắc chắn muốn xóa tàu {so_hieu} ({class_name}) không?\nLưu ý: Mọi lịch sử phát hiện (shiplog) liên quan cũng sẽ bị xóa (cascade).', parent=self.root):
            try:
                conn = self.get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM ship WHERE so_hieu=?', (so_hieu,))
                    conn.commit()
                    conn.close()
                    messagebox.showinfo('Thành công', f'Đã xóa tàu {so_hieu}', parent=self.root)
                    self.refresh_ship_list()
                    self.view.ship_info_label.config(text='Vui lòng chọn một tàu từ danh sách để xem chi tiết thông tin và lịch sử.', fg='#7f8c8d', font=('Segoe UI', 10))
                    self.view.ship_img_canvas.delete('all')
                    self.view.ship_img_canvas.create_text(175, 110, text='📷 Không có ảnh đại diện', fill='#95a5a6')
                    for i in self.view.ship_history_tree.get_children():
                        self.view.ship_history_tree.delete(i)
            except Exception as e:
                messagebox.showerror('Lỗi', f'Không thể xóa: {e}', parent=self.root)

    def load_ship_history(self, so_hieu):
        for i in self.view.ship_history_tree.get_children():
            self.view.ship_history_tree.delete(i)
        try:
            conn = self.get_db_connection()
            if not conn:
                return
            cursor = conn.cursor()
            cursor.execute('\n                SELECT gio_phat_hien, loai_tau, do_tin_cay_ocr\n                FROM shiplog\n                WHERE so_hieu = ?\n                ORDER BY gio_phat_hien DESC\n            ', (so_hieu,))
            rows = cursor.fetchall()
            for r in rows:
                dt_str = r.gio_phat_hien.strftime('%Y-%m-%d %H:%M:%S') if r.gio_phat_hien else ''
                conf = f'{r.do_tin_cay_ocr:.1f}%' if r.do_tin_cay_ocr else 'N/A'
                self.view.ship_history_tree.insert('', 'end', values=(dt_str, r.loai_tau, conf))
            conn.close()
        except Exception as e:
            print(f'Lỗi truy xuất lịch sử tàu {so_hieu}: {e}')

    def open_add_ship_dialog(self):
        if not AuthController.has_permission(Permission.MANAGE_SHIPS):
            messagebox.showerror('Quyền hạn chế', 'Bạn không có quyền thêm tàu. Liên hệ quản trị viên.', parent=self.root)
            return
        self.add_dialog = AddShipView(self.root, self.class_options)
        self.add_dialog.set_save_command(self.save_new_ship)

    def save_new_ship(self):
        data = self.add_dialog.get_data()
        so_hieu = data['so_hieu']
        class_name = data['class_name']
        anh_goc = data['anh_dai_dien']
        mo_ta = data['mo_ta']
        if not so_hieu:
            messagebox.showwarning('Thiếu thông tin', 'Vui lòng nhập Số hiệu tàu!', parent=self.add_dialog)
            return
        anh_dai_dien = ''
        if anh_goc and os.path.exists(anh_goc):
            try:
                ext = os.path.splitext(anh_goc)[1]
                if not ext:
                    ext = '.jpg'
                new_filename = f'profile_{so_hieu}_{int(time.time())}{ext}'
                new_path = os.path.join(self.profile_images_dir, new_filename)
                shutil.copy2(anh_goc, new_path)
                anh_dai_dien = f'outputs/ship_profiles/{new_filename}'
            except Exception as e:
                print(f'Lỗi copy ảnh: {e}')
                anh_dai_dien = anh_goc
        try:
            conn = self.get_db_connection()
            if not conn:
                messagebox.showerror('Lỗi', 'Không thể kết nối CSDL', parent=self.add_dialog)
                return
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM ship WHERE so_hieu=?', (so_hieu,))
            if cursor.fetchone()[0] > 0:
                messagebox.showwarning('Trùng lặp', f'Số hiệu {so_hieu} đã tồn tại trong hệ thống!', parent=self.add_dialog)
                conn.close()
                return
            cursor.execute('\n                INSERT INTO ship (so_hieu, loai_tau, mo_ta, anh_dai_dien)\n                VALUES (?, ?, ?, ?)\n            ', (so_hieu, class_name, mo_ta, anh_dai_dien))
            conn.commit()
            conn.close()
            messagebox.showinfo('Thành công', f'Đã thêm tàu {so_hieu} thành công!', parent=self.add_dialog)
            self.add_dialog.close_dialog()
            self.refresh_ship_list()
        except Exception as e:
            messagebox.showerror('Lỗi CSDL', f'Có lỗi xảy ra: {e}', parent=self.add_dialog)

    def open_edit_ship_dialog(self):
        selection = self.view.ship_tree.selection()
        if not selection:
            messagebox.showwarning('Cảnh báo', 'Vui lòng chọn một tàu trong danh sách để sửa!', parent=self.root)
            return
        item_id = selection[0]
        values = self.view.ship_tree.item(item_id, 'values')
        so_hieu = values[0]
        class_name = values[1]
        mo_ta = 'Không có mô tả'
        try:
            conn = self.get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('SELECT mo_ta FROM ship WHERE so_hieu=?', (so_hieu,))
                row = cursor.fetchone()
                if row and row.mo_ta:
                    mo_ta = row.mo_ta
                conn.close()
        except Exception:
            pass
        ship_data = {'so_hieu': so_hieu, 'class_name': class_name, 'mo_ta': mo_ta}
        self.edit_dialog = EditShipView(self.root, self.class_options)
        self.edit_dialog.load_data(ship_data)
        self.edit_dialog.set_save_command(self.update_ship)

    def update_ship(self):
        data = self.edit_dialog.get_data()
        so_hieu = data['so_hieu']
        class_name = data['class_name']
        anh_moi = data['anh_dai_dien_moi']
        mo_ta = data['mo_ta']
        anh_dai_dien = None
        if anh_moi and os.path.exists(anh_moi):
            try:
                ext = os.path.splitext(anh_moi)[1]
                if not ext:
                    ext = '.jpg'
                new_filename = f'profile_{so_hieu}_{int(time.time())}{ext}'
                new_path = os.path.join(self.profile_images_dir, new_filename)
                shutil.copy2(anh_moi, new_path)
                anh_dai_dien = f'outputs/ship_profiles/{new_filename}'
            except Exception as e:
                print(f'Lỗi copy ảnh: {e}')
                anh_dai_dien = anh_moi
        try:
            conn = self.get_db_connection()
            if not conn:
                messagebox.showerror('Lỗi', 'Không thể kết nối CSDL', parent=self.edit_dialog)
                return
            cursor = conn.cursor()
            if anh_dai_dien:
                cursor.execute('\n                    UPDATE ship \n                    SET loai_tau = ?, mo_ta = ?, anh_dai_dien = ?\n                    WHERE so_hieu = ?\n                ', (class_name, mo_ta, anh_dai_dien, so_hieu))
            else:
                cursor.execute('\n                    UPDATE ship \n                    SET loai_tau = ?, mo_ta = ?\n                    WHERE so_hieu = ?\n                ', (class_name, mo_ta, so_hieu))
            conn.commit()
            conn.close()
            messagebox.showinfo('Thành công', f'Đã cập nhật thông tin tàu {so_hieu}!', parent=self.edit_dialog)
            self.edit_dialog.close_dialog()
            self.refresh_ship_list()
            selection = self.view.ship_tree.selection()
            if selection:
                self.on_ship_selected(None)
        except Exception as e:
            messagebox.showerror('Lỗi CSDL', f'Có lỗi xảy ra: {e}', parent=self.edit_dialog)
