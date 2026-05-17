"""
微信数据库解密模块
从 wechat-decrypt/monitor.py 提取核心解密逻辑，去除监听/UI依赖
依赖: pycryptodome (AES)
"""
import hashlib, os, sqlite3
from Crypto.Cipher import AES

PAGE_SZ = 4096
KEY_SZ = 32
SALT_SZ = 16
IV_SZ = 16
RESERVE_SZ = 80
SQLITE_HDR = b'SQLite format 3\x00'


def decrypt_page(enc_key, page_data, pgno):
    iv = page_data[PAGE_SZ - RESERVE_SZ : PAGE_SZ - RESERVE_SZ + IV_SZ]
    if pgno == 1:
        encrypted = page_data[SALT_SZ : PAGE_SZ - RESERVE_SZ]
        cipher = AES.new(enc_key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(encrypted)
        page = bytearray(SQLITE_HDR + decrypted + b'\x00' * RESERVE_SZ)
        return bytes(page)
    else:
        encrypted = page_data[:PAGE_SZ - RESERVE_SZ]
        cipher = AES.new(enc_key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(encrypted)
        return decrypted + b'\x00' * RESERVE_SZ


def decrypt_db_to_memory(db_path, enc_key):
    """解密DB到内存中的bytes"""
    file_size = os.path.getsize(db_path)
    total_pages = file_size // PAGE_SZ
    if file_size % PAGE_SZ != 0:
        total_pages += 1

    chunks = []
    with open(db_path, 'rb') as fin:
        for pgno in range(1, total_pages + 1):
            page = fin.read(PAGE_SZ)
            if len(page) < PAGE_SZ:
                if len(page) > 0:
                    page = page + b'\x00' * (PAGE_SZ - len(page))
                else:
                    break
            decrypted = decrypt_page(enc_key, page, pgno)
            chunks.append(decrypted)

    return b''.join(chunks)


def decrypt_db_to_sqlite(db_path, enc_key):
    """解密DB并返回sqlite3连接 (内存数据库)"""
    data = decrypt_db_to_memory(db_path, enc_key)
    tmp_path = db_path + ".tmp_monitor"
    with open(tmp_path, 'wb') as f:
        f.write(data)
    conn = sqlite3.connect(tmp_path)
    conn.row_factory = sqlite3.Row
    return conn, tmp_path
