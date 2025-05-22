import unittest
from pathlib import Path
import tempfile
import shutil

def validate_input_directory(dir_path: Path) -> bool:
    """验证输入目录有效性"""
    dir_path = dir_path.expanduser().resolve()
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {dir_path}")
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {dir_path}")
    return True

def ensure_directory(path: Path) -> Path:
    """确保目录存在"""
    path = path.expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path

def cleanup_empty_directories(root_dir: Path):
    """清理空目录（递归）"""
    for dirpath in sorted(root_dir.glob("*/"), key=lambda p: len(p.parts), reverse=True):
        cleanup_empty_directories(dirpath)
    if root_dir.is_dir() and not any(root_dir.iterdir()):
        root_dir.rmdir()

def get_first_level_subdirectories(dir_path: Path) -> list[Path]:
    """获取所有一级子目录"""
    dir_path = dir_path.expanduser().resolve()
    validate_input_directory(dir_path)
    return [d for d in dir_path.iterdir() if d.is_dir()]

class TestDirectoryFunctions(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        
        # 创建测试子目录
        self.sub_dir = self.test_dir / "subdir"  # 保留这个用于兼容其他测试
        self.sub_dir.mkdir()
        (self.sub_dir / "file.txt").touch()
        
        # 创建3个专门用于子目录测试的目录
        self.sub_dirs = [
            self.test_dir / "subdir1",
            self.test_dir / "subdir2",
            self.test_dir / "subdir3"
        ]
        for d in self.sub_dirs:
            d.mkdir()
        
        # 创建测试文件
        (self.test_dir / "file.txt").touch()
        (self.sub_dirs[0] / "nested").mkdir()
        (self.sub_dirs[1] / "file_in_subdir.txt").touch()
        
        # 空目录
        self.empty_dir = self.test_dir / "empty_dir"
        self.empty_dir.mkdir()
        
        # 无效路径
        self.nonexistent_dir = self.test_dir / "nonexistent"

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_validate_input_directory_valid(self):
        self.assertTrue(validate_input_directory(self.test_dir))
        self.assertTrue(validate_input_directory(self.sub_dir))

    def test_validate_input_directory_nonexistent(self):
        with self.assertRaises(FileNotFoundError):
            validate_input_directory(self.nonexistent_dir)

    def test_validate_input_directory_not_a_dir(self):
        file_path = self.sub_dir / "file.txt"
        with self.assertRaises(NotADirectoryError):
            validate_input_directory(file_path)

    def test_ensure_directory_new(self):
        new_dir = self.test_dir / "new_dir"
        result = ensure_directory(new_dir)
        self.assertTrue(new_dir.exists())
        self.assertTrue(new_dir.is_dir())
        self.assertEqual(result, new_dir.resolve())

    def test_ensure_directory_existing(self):
        result = ensure_directory(self.sub_dir)
        self.assertTrue(self.sub_dir.exists())
        self.assertEqual(result, self.sub_dir.resolve())

    def test_ensure_directory_nested(self):
        nested_dir = self.test_dir / "a" / "b" / "c"
        result = ensure_directory(nested_dir)
        self.assertTrue(nested_dir.exists())
        self.assertEqual(result, nested_dir.resolve())

    def test_get_first_level_subdirectories(self):
        subdirs = get_first_level_subdirectories(self.test_dir)
        expected = set(self.sub_dirs + [self.sub_dir, self.empty_dir])
        self.assertEqual(set(subdirs), expected)
        self.assertNotIn(self.test_dir / "file.txt", subdirs)
        self.assertNotIn(self.sub_dirs[0] / "nested", subdirs)

    def test_get_first_level_subdirectories_empty(self):
        empty_dir = self.test_dir / "empty"
        empty_dir.mkdir()
        subdirs = get_first_level_subdirectories(empty_dir)
        self.assertEqual(subdirs, [])

    def test_cleanup_empty_directories(self):
        empty_subdir = self.empty_dir / "sub1" / "sub2"
        empty_subdir.mkdir(parents=True)
        self.assertTrue(empty_subdir.exists())
        
        cleanup_empty_directories(self.empty_dir)
        
        self.assertFalse(empty_subdir.exists())
        self.assertFalse((self.empty_dir / "sub1").exists())
        self.assertFalse(self.empty_dir.exists())
        self.assertTrue(self.sub_dir.exists())

    def test_cleanup_with_non_empty_dirs(self):
        self.assertTrue(any(self.sub_dir.iterdir()))
        cleanup_empty_directories(self.test_dir)
        self.assertTrue(self.sub_dir.exists())
        self.assertTrue((self.sub_dir / "file.txt").exists())

if __name__ == "__main__":
    unittest.main()