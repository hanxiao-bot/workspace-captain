#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志清理脚本 (log_cleaner.py)
==========================

一个用于自动清理过期日志文件的 Python 脚本，基于标准库实现，无需额外依赖。

功能特性
--------
- 递归扫描指定目录下的日志文件（支持通配符如 *.log, *.txt）
- 根据文件修改时间删除 N 天前的日志
- 支持排除指定目录或文件
- 清理后记录详细日志（操作人、时间、删除的文件及大小）

用法示例
--------
    # 删除 /var/log 目录下 7 天前的所有 .log 文件
    python cleaner.py /var/log --pattern "*.log" --days 7

    # 删除 /home/logs 下 30 天前的 .log 和 .txt 文件，排除 backup 子目录
    python cleaner.py /home/logs --pattern "*.log" "*.txt" --days 30 --exclude backup

    # 模拟运行（不实际删除，仅预览将删除的文件）
    python cleaner.py /tmp/logs --pattern "*.log" --days 7 --dry-run

    # 删除前显示详细信息
    python cleaner.py /var/log --pattern "*.log" --days 7 -v

    # 指定日志输出文件
    python cleaner.py /var/log --pattern "*.log" --days 7 --log-file /var/log/cleaner.log

作者：Captain Agent
日期：2026-03-28
"""

import os
import sys
import re
import argparse
import shutil
import logging
import json
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Set, Optional


# ------------------------------------------------------------
# 配置区
# ------------------------------------------------------------
# 默认保留天数
DEFAULT_DAYS = 7

# 默认日志格式
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 操作日志文件（记录删除操作）
OPERATION_LOG_FILE = ".log_cleaner_history.json"


# ------------------------------------------------------------
# 辅助函数
# ------------------------------------------------------------

def format_size(size_bytes: int) -> str:
    """
    将字节数格式化为人类可读的大小字符串。

    Args:
        size_bytes: 文件大小（字节）

    Returns:
        格式化后的大小字符串，如 "1.5 MB"
    """
    if size_bytes < 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.2f} {units[unit_index]}"


def get_username() -> str:
    """
    获取当前用户名。

    Returns:
        用户名字符串
    """
    return os.environ.get("USER", "unknown")


def load_operation_history(log_dir: Path) -> List[dict]:
    """
    从 JSON 文件加载历史操作记录。

    Args:
        log_dir: 日志清理操作的目录

    Returns:
        历史操作记录列表
    """
    history_file = log_dir / OPERATION_LOG_FILE
    if not history_file.exists():
        return []

    try:
        with open(history_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logging.warning(f"无法读取历史记录文件: {e}")
        return []


def save_operation_history(log_dir: Path, records: List[dict]) -> None:
    """
    将操作记录保存到 JSON 文件。

    Args:
        log_dir: 日志清理操作的目录
        records: 操作记录列表
    """
    history_file = log_dir / OPERATION_LOG_FILE

    try:
        # 保留最近 1000 条记录
        records = records[-1000:]

        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logging.error(f"无法保存操作历史记录: {e}")


def match_any_pattern(path: Path, patterns: List[str]) -> bool:
    """
    检查路径是否匹配任意一个通配符模式。

    Args:
        path: 要检查的路径
        patterns: 通配符模式列表（如 *.log）

    Returns:
        如果匹配返回 True，否则返回 False
    """
    path_str = str(path)
    path_name = path.name

    for pattern in patterns:
        # 支持带路径的模式，如 "logs/*.log"
        if "/" in pattern or "\\" in pattern:
            # 转换为正则表达式
            regex_pattern = pattern.replace(".", r"\.").replace("*", ".*").replace("?", ".")
            regex_pattern = f"^{regex_pattern}$"
            try:
                if re.match(regex_pattern, path_str):
                    return True
            except re.error:
                pass
        else:
            # 简单文件名模式
            regex_pattern = pattern.replace(".", r"\.").replace("*", ".*").replace("?", ".")
            regex_pattern = f"^{regex_pattern}$"
            try:
                if re.match(regex_pattern, path_name):
                    return True
            except re.error:
                pass

    return False


def is_excluded(path: Path, exclude_patterns: Set[str]) -> bool:
    """
    检查路径是否在排除列表中。

    Args:
        path: 要检查的路径
        exclude_patterns: 排除模式集合

    Returns:
        如果应该排除返回 True，否则返回 False
    """
    path_str = str(path)

    for exclude in exclude_patterns:
        # 精确匹配路径
        if str(path) == exclude:
            return True
        # 目录匹配（检查路径的前缀）
        if path.is_dir() and (exclude.endswith("/") or exclude.endswith("\\")):
            if path_str.startswith(exclude.rstrip("/\\")):
                return True
        # 文件相对于扫描目录的路径匹配
        if exclude in path_str:
            return True

    return False


def remove_readonly(func, path, exc_info):
    """
    移除只读属性后重试删除的回调函数。
    用于处理只读文件的删除。
    """
    os.chmod(path, stat.S_IWRITE)
    func(path)


# ------------------------------------------------------------
# 核心类
# ------------------------------------------------------------

class LogCleaner:
    """
    日志清理器类。

    负责扫描指定目录、识别过期文件、执行删除操作并记录日志。

    Attributes:
        scan_dir: 要扫描的根目录
        patterns: 文件名匹配模式列表
        days: 保留天数（超过此天数的文件将被删除）
        exclude: 排除的路径集合
        dry_run: 是否为模拟运行模式
        verbose: 是否显示详细信息
    """

    def __init__(
        self,
        scan_dir: Path,
        patterns: List[str],
        days: int = DEFAULT_DAYS,
        exclude: Optional[Set[str]] = None,
        dry_run: bool = False,
        verbose: bool = False,
        log_file: Optional[Path] = None
    ):
        """
        初始化日志清理器。

        Args:
            scan_dir: 要扫描的目录路径
            patterns: 文件名匹配模式列表
            days: 保留天数（默认 7 天）
            exclude: 要排除的路径集合
            dry_run: 是否模拟运行（不实际删除）
            verbose: 是否输出详细信息
            log_file: 可选的日志输出文件路径
        """
        self.scan_dir = scan_dir
        self.patterns = patterns
        self.days = days
        self.exclude = exclude or set()
        self.dry_run = dry_run
        self.verbose = verbose

        # 计算截止时间（当前时间 - 保留天数）
        self.cutoff_time = datetime.now(timezone.utc).timestamp() - (days * 86400)

        # 操作统计
        self.scanned_count = 0
        self.excluded_count = 0
        self.deleted_count = 0
        self.deleted_size = 0
        self.error_count = 0
        self.errors: List[str] = []

        # 设置日志记录器
        self._setup_logger(log_file)

    def _setup_logger(self, log_file: Optional[Path]) -> None:
        """
        配置日志记录器。

        Args:
            log_file: 可选的日志输出文件
        """
        handlers = [logging.StreamHandler(sys.stdout)]

        if log_file:
            handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

        logging.basicConfig(
            level=logging.DEBUG if self.verbose else logging.INFO,
            format=LOG_FORMAT,
            datefmt=LOG_DATE_FORMAT,
            handlers=handlers
        )

    def _log_summary(self, action: str, file_path: Path, file_size: int) -> None:
        """
        记录操作摘要。

        Args:
            action: 操作类型
            file_path: 文件路径
            file_size: 文件大小
        """
        if self.verbose:
            logging.info(f"{action}: {file_path} ({format_size(file_size)})")

    def _record_error(self, file_path: Path, error: str) -> None:
        """
        记录错误信息。

        Args:
            file_path: 出错的文件路径
            error: 错误描述
        """
        self.error_count += 1
        error_msg = f"{file_path}: {error}"
        self.errors.append(error_msg)
        logging.error(f"删除失败: {error_msg}")

    def scan(self) -> List[Path]:
        """
        扫描目录，查找所有匹配模式且超过保留期限的文件。

        Returns:
            需要删除的文件路径列表
        """
        to_delete: List[Path] = []

        logging.info(f"开始扫描目录: {self.scan_dir}")
        logging.info(f"匹配模式: {', '.join(self.patterns)}")
        logging.info(f"保留天数: {self.days} 天")
        logging.info(f"截止时间: {datetime.fromtimestamp(self.cutoff_time, tz=timezone.utc)}")

        if self.exclude:
            logging.info(f"排除路径: {', '.join(self.exclude)}")

        if self.dry_run:
            logging.warning("⚠️  [DRY-RUN 模式] 不会实际删除任何文件")

        # 递归遍历目录
        for root, dirs, files in os.walk(self.scan_dir):
            root_path = Path(root)

            # 过滤掉被排除的目录
            dirs[:] = [d for d in dirs if not self._should_exclude_dir(root_path / d)]

            for filename in files:
                file_path = root_path / filename
                self.scanned_count += 1

                # 检查是否在排除列表
                if is_excluded(file_path, self.exclude):
                    self.excluded_count += 1
                    if self.verbose:
                        self._log_summary("排除", file_path, 0)
                    continue

                # 检查是否匹配模式
                if not match_any_pattern(file_path, self.patterns):
                    continue

                # 检查文件修改时间
                try:
                    mtime = file_path.stat().st_mtime
                except OSError as e:
                    self._record_error(file_path, str(e))
                    continue

                if mtime < self.cutoff_time:
                    to_delete.append(file_path)

        return to_delete

    def _should_exclude_dir(self, dir_path: Path) -> bool:
        """
        检查目录是否应该被排除（不扫描其内容）。

        Args:
            dir_path: 目录路径

        Returns:
            如果应该排除返回 True
        """
        # 检查精确匹配
        if str(dir_path) in self.exclude:
            return True

        # 检查父路径是否在排除列表
        for exclude in self.exclude:
            if exclude.endswith("/") or exclude.endswith("\\"):
                parent = exclude.rstrip("/\\")
                if str(dir_path).startswith(parent):
                    return True

        return False

    def delete(self, to_delete: List[Path]) -> None:
        """
        执行删除操作。

        Args:
            to_delete: 要删除的文件路径列表
        """
        if not to_delete:
            logging.info("没有需要删除的文件")
            return

        logging.info(f"找到 {len(to_delete)} 个过期文件需要处理")

        # 先排序，确保按路径顺序处理
        to_delete.sort()

        for file_path in to_delete:
            try:
                file_size = file_path.stat().st_size

                if self.dry_run:
                    self._log_summary("[DRY-RUN] 将删除", file_path, file_size)
                else:
                    # 删除文件
                    file_path.unlink()
                    self._log_summary("已删除", file_path, file_size)

                self.deleted_count += 1
                self.deleted_size += file_size

            except PermissionError:
                # 尝试移除只读属性后重试
                try:
                    os.chmod(file_path, stat.S_IWRITE)
                    file_path.unlink()
                    self._log_summary("已删除（已移除只读属性）", file_path, file_size)
                    self.deleted_count += 1
                    self.deleted_size += file_size
                except OSError as e:
                    self._record_error(file_path, str(e))
            except OSError as e:
                self._record_error(file_path, str(e))

    def save_record(self) -> dict:
        """
        保存本次操作记录到历史日志。

        Returns:
            操作记录字典
        """
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "username": get_username(),
            "scan_dir": str(self.scan_dir),
            "patterns": self.patterns,
            "days": self.days,
            "scanned": self.scanned_count,
            "excluded": self.excluded_count,
            "deleted": self.deleted_count,
            "deleted_size": self.deleted_size,
            "deleted_size_formatted": format_size(self.deleted_size),
            "errors": self.error_count,
            "error_details": self.errors,
            "dry_run": self.dry_run
        }

        # 保存到扫描目录下的历史记录文件
        if not self.dry_run:
            history = load_operation_history(self.scan_dir)
            history.append(record)
            save_operation_history(self.scan_dir, history)

        return record

    def print_summary(self) -> None:
        """
        打印操作摘要。
        """
        logging.info("=" * 50)
        logging.info("📊 操作摘要")
        logging.info("=" * 50)
        logging.info(f"扫描目录: {self.scan_dir}")
        logging.info(f"匹配模式: {', '.join(self.patterns)}")
        logging.info(f"保留天数: {self.days} 天")
        logging.info(f"扫描文件数: {self.scanned_count}")
        logging.info(f"排除文件数: {self.excluded_count}")

        if self.dry_run:
            logging.info(f"【模拟】将删除: {self.deleted_count} 个文件 ({format_size(self.deleted_size)})")
        else:
            logging.info(f"已删除: {self.deleted_count} 个文件 ({format_size(self.deleted_size)})")

        if self.error_count > 0:
            logging.warning(f"删除失败: {self.error_count} 个文件")

        logging.info("=" * 50)


# ------------------------------------------------------------
# 主程序
# ------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """
    解析命令行参数。

    Returns:
        解析后的参数对象
    """
    parser = argparse.ArgumentParser(
        description="日志清理脚本 - 递归删除过期日志文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  %(prog)s /var/log --pattern "*.log" --days 7
  %(prog)s /home/logs --pattern "*.log" "*.txt" --days 30 --exclude backup --exclude temp
  %(prog)s /tmp/logs --pattern "*.log" --days 7 --dry-run -v
  %(prog)s /var/log --pattern "*.log" --days 7 --log-file /var/log/cleaner.log
        """
    )

    parser.add_argument(
        "scan_dir",
        type=Path,
        help="要扫描的根目录路径"
    )

    parser.add_argument(
        "--pattern", "-p",
        nargs="+",
        default=["*.*"],
        metavar="PATTERN",
        help=f"文件匹配模式（支持通配符），默认为 *.*。示例: *.log *.txt *.gz"
    )

    parser.add_argument(
        "--days", "-d",
        type=int,
        default=DEFAULT_DAYS,
        metavar="N",
        help=f"保留天数，超过此天数的文件将被删除（默认: {DEFAULT_DAYS}）"
    )

    parser.add_argument(
        "--exclude", "-e",
        nargs="+",
        default=[],
        metavar="PATH",
        help="要排除的目录或文件路径（支持相对路径或绝对路径）"
    )

    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="模拟运行模式，不实际删除文件，仅预览将删除的文件"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细信息"
    )

    parser.add_argument(
        "--log-file", "-l",
        type=Path,
        default=None,
        metavar="FILE",
        help="将操作日志写入指定文件（默认输出到标准输出）"
    )

    parser.add_argument(
        "--no-record",
        action="store_true",
        help="不保存操作记录到 JSON 文件"
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> bool:
    """
    验证命令行参数的合法性。

    Args:
        args: 解析后的参数对象

    Returns:
        参数合法返回 True，否则返回 False
    """
    # 检查扫描目录是否存在
    if not args.scan_dir.exists():
        logging.error(f"错误: 目录不存在: {args.scan_dir}")
        return False

    if not args.scan_dir.is_dir():
        logging.error(f"错误: 路径不是目录: {args.scan_dir}")
        return False

    # 检查保留天数
    if args.days < 0:
        logging.error("错误: 保留天数不能为负数")
        return False

    # 检查模式列表
    if not args.pattern:
        logging.error("错误: 必须指定至少一个匹配模式")
        return False

    return True


def main() -> int:
    """
    主程序入口。

    Returns:
        退出码（0 表示成功，非 0 表示失败）
    """
    args = parse_args()

    # 验证参数
    if not validate_args(args):
        return 1

    # 转换排除路径为绝对路径
    exclude_paths: Set[str] = set()
    for ex in args.exclude:
        # 如果是绝对路径，直接使用
        if os.path.isabs(ex):
            exclude_paths.add(ex)
        else:
            # 否则相对于扫描目录
            exclude_paths.add(str(args.scan_dir / ex))

    # 创建清理器实例
    cleaner = LogCleaner(
        scan_dir=args.scan_dir,
        patterns=args.pattern,
        days=args.days,
        exclude=exclude_paths,
        dry_run=args.dry_run,
        verbose=args.verbose,
        log_file=args.log_file
    )

    try:
        # 扫描文件
        to_delete = cleaner.scan()

        # 执行删除
        cleaner.delete(to_delete)

        # 保存记录
        if not args.no_record:
            record = cleaner.save_record()

            if args.verbose:
                logging.debug(f"操作记录已保存: {json.dumps(record, indent=2, ensure_ascii=False)}")

        # 打印摘要
        cleaner.print_summary()

        # 根据结果返回退出码
        if cleaner.error_count > 0:
            return 2  # 部分文件删除失败

        return 0

    except KeyboardInterrupt:
        logging.warning("\n操作被用户中断")
        return 130
    except Exception as e:
        logging.exception(f"发生未预期的错误: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
