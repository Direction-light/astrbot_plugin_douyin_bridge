# 只放测试用的空文件。
# 作用：让 pytest 把仓库根目录加进 sys.path，这样 `pytest` 和
# `python -m pytest` 都能直接 `from core.xxx import ...`。
