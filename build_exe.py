import importlib.util
import os
import sys
import shutil
import subprocess
from pathlib import Path


def _pkg_installed(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def build_pyinstaller_cmd(project_root: Path) -> list:
    main_script = project_root / 'src' / 'main.py'
    hooks_dir = project_root / 'hooks'
    sep = os.pathsep

    # Tạo thư mục hooks nếu chưa tồn tại
    if not hooks_dir.exists():
        print(f'>> Tạo thư mục hooks tại: {hooks_dir}')
        hooks_dir.mkdir(exist_ok=True)

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--noconfirm',
        '--onedir',
        '--windowed',
        '--name', 'ShipDetection',
        f'--paths={project_root}',
        f'--additional-hooks-dir={hooks_dir}',
        '--collect-submodules', 'src',
        '--hidden-import', 'pyodbc',
        '--hidden-import', 'tkcalendar',
        '--hidden-import', 'matplotlib.backends.backend_tkagg',
        '--hidden-import', 'src.engines.ocr_engine',
        '--hidden-import', 'paddle',
        '--hidden-import', 'paddleocr',
        '--hidden-import', 'torch',
        '--add-data', f'src/trackers{sep}src/trackers',
        '--add-data', f'picture{sep}picture',
    ]

    for pkg in (
        'Cython',
        'paddle',
        'paddleocr',
        'paddlex',
        'shapely',
        'pyclipper',
        'skimage',
        'imgaug',
        'lmdb',
        'rapidfuzz',
    ):
        if _pkg_installed(pkg):
            cmd.extend(['--collect-all', pkg])
            print(f'>> Gói thêm package: {pkg}')

    if _pkg_installed('Cython'):
        try:
            import Cython
            utility = Path(Cython.__file__).resolve().parent / 'Utility'
            if utility.is_dir():
                cmd.extend(['--add-data', f'{utility}{sep}Cython/Utility'])
                print(f'>> Gói Cython Utility: {utility}')
        except Exception as e:
            print(f'>> Cảnh báo: không gói được Cython Utility ({e})')

    cmd.append(str(main_script))
    return cmd


def run_build():
    print('==================================================')
    print('   BẮT ĐẦU ĐÓNG GÓI HỆ THỐNG PHÁT HIỆN TÀU THUYỀN   ')
    print('==================================================\n')
    
    # Kiểm tra các package quan trọng
    print('>> Kiểm tra các thư viện bắt buộc:')
    required_pkgs = ['PyInstaller', 'torch', 'paddle', 'paddleocr', 'ultralytics', 'pyodbc']
    missing_pkgs = []
    
    for pkg in required_pkgs:
        if _pkg_installed(pkg):
            print(f'   ✓ {pkg}')
        else:
            print(f'   ✗ {pkg} (THIẾU)')
            missing_pkgs.append(pkg)
    
    if missing_pkgs:
        print(f'\n⚠️  Cảnh báo: Thiếu các package: {", ".join(missing_pkgs)}')
        print('   Chạy: pip install -r requirements.txt')
        print('   Hoặc: pip install PyInstaller torch paddle paddleocr\n')
    
    # Kiểm tra PyInstaller
    try:
        import PyInstaller
        print('\n>> Đã tìm thấy PyInstaller.')
    except ImportError:
        print('\n>> Không tìm thấy PyInstaller. Đang cài đặt...')
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], check=True)
            print('>> Đã cài đặt PyInstaller thành công.')
        except Exception as e:
            print(f'❌ Lỗi cài đặt PyInstaller: {e}')
            sys.exit(1)

    project_root = Path(__file__).resolve().parent
    dist_dir = project_root / 'dist'
    build_dir = project_root / 'build'
    if dist_dir.exists():
        print('>> Đang dọn dẹp thư mục dist cũ...')
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        print('>> Đang dọn dẹp thư mục build cũ...')
        shutil.rmtree(build_dir)

    cmd = build_pyinstaller_cmd(project_root)
    print('\n>> Đang chạy lệnh đóng gói:')
    print(' '.join(cmd))
    print('\n(Quá trình này có thể mất 10-20 phút do PyTorch + PaddleOCR...)\n')
    try:
        subprocess.run(cmd, check=True)
        print('\n' + '='*50)
        print('✓ ĐÓNG GÓI THÀNH CÔNG!')
        print('='*50)
    except subprocess.CalledProcessError as e:
        print('\n' + '='*50)
        print(f'❌ LỖI trong quá trình đóng gói')
        print('='*50)
        print(f'Chi tiết: {e}')
        print('\n💡 Các giải pháp:')
        print('  1. Kiểm tra: pip list | grep -E "PyInstaller|torch|paddle"')
        print('  2. Nâng cấp pip: python -m pip install --upgrade pip')
        print('  3. Cài đầy đủ: pip install -r requirements.txt')
        print('  4. Xóa cache: rmdir /s build dist .spec')
        sys.exit(1)

    exe_dist_dir = dist_dir / 'ShipDetection'
    if exe_dist_dir.exists():
        print('\n>> Đang thiết lập các thư mục dữ liệu...')
        
        models_dist = exe_dist_dir / 'models'
        models_dist.mkdir(exist_ok=True)
        models_src = project_root / 'models'
        if models_src.exists():
            for f in models_src.glob('*'):
                if f.is_file():
                    try:
                        shutil.copy2(f, models_dist)
                    except Exception as e:
                        print(f'   ⚠️  Lỗi sao chép {f.name}: {e}')
            print('   ✓ Đã sao chép models.')
        else:
            print('   ⚠️  Thư mục models không tìm thấy.')
        
        videos_dist = exe_dist_dir / 'videos'
        videos_dist.mkdir(exist_ok=True)
        videos_src = project_root / 'videos'
        if videos_src.exists():
            for f in videos_src.glob('*'):
                if f.is_file():
                    try:
                        shutil.copy2(f, videos_dist)
                    except Exception as e:
                        print(f'   ⚠️  Lỗi sao chép {f.name}: {e}')
            print('   ✓ Đã sao chép videos.')
        
        outputs_dist = exe_dist_dir / 'outputs'
        outputs_dist.mkdir(exist_ok=True)
        print('   ✓ Đã tạo thư mục outputs.')
        
        print('\n' + '='*50)
        print('✓ ỨNG DỤNG ĐÃ SẴN SÀNG!')
        print('='*50)
        print(f'📁 Thư mục: {exe_dist_dir}')
        print(f'🎯 Chạy: {exe_dist_dir / "ShipDetection.exe"}')
    else:
        print(f'\n❌ Không tìm thấy thư mục dist:\n{exe_dist_dir}')


if __name__ == '__main__':
    run_build()
