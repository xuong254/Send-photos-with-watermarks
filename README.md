
# 📸 Gửi Ảnh Có Gắn Watermark – Đề tài 9

## 📝 Mô tả

Ứng dụng mô phỏng quá trình **gửi ảnh có gắn watermark bảo vệ bản quyền** lên nền tảng chia sẻ nội dung. Ảnh được:

- ✅ Gắn watermark để xác định nguồn gốc
- 🔐 Mã hóa bằng thuật toán **DES**
- ✍️ Ký số bằng thuật toán **RSA 2048-bit (PKCS#1 v1.5 + SHA-512)**
- 🧾 Kiểm tra tính toàn vẹn bằng **SHA-512**

Giao diện Web gồm:
- 👤 **Người gửi (Sender)**
- 📥 **Người nhận (Receiver)**

---

## 🎯 Yêu cầu kỹ thuật

| Thành phần       | Công nghệ sử dụng                              |
|------------------|------------------------------------------------|
| Mã hóa           | DES (Cipher Block Chaining)                   |
| Ký số & Trao khóa| RSA 2048-bit, PKCS#1 v1.5, SHA-512            |
| Kiểm tra toàn vẹn| SHA-512                                       |
| Watermark        | In text đè lên ảnh bằng Pillow (PIL)          |

---

## 🔁 Luồng xử lý

### 1. 🤝 Handshake

- **Người gửi** → `"Hello!"`  
- **Người nhận** → `"Ready!"`

---

### 2. 🔐 Trao khóa & Ký số

- Người gửi tạo metadata:
  ```
  Tên file + timestamp + watermark
  ```
- Ký metadata bằng **private key (RSA/SHA-512)**
- Mã hóa **session key DES** bằng **public key người nhận**

---

### 3. 🧩 Mã hóa & Đóng gói

- Thêm watermark vào ảnh
- Tạo `IV` ngẫu nhiên
- Mã hóa ảnh bằng **DES**
- Tính hash:
  ```
  SHA-512(IV || ciphertext)
  ```

**Tạo file output.zip gồm:**
```
cipher.des
iv.txt
signature.sig
hash.txt
metadata.txt
session_key_rsa.bin
```

---

### 4. 📬 Phía người nhận

- Giải nén và kiểm tra:
  - ✅ Hash SHA-512
  - ✅ Chữ ký RSA
- Nếu hợp lệ:
  - 🔓 Giải mã ảnh bằng DES
  - 🖼️ Hiển thị ảnh
  - ↩️ Gửi "ACK" về người gửi
- Nếu lỗi:
  - ❌ Gửi "NACK" (sai hash hoặc chữ ký)

---

## 🗂️ Cấu trúc thư mục

```
BAITAPLON/
├── app_gui.py              # Web người gửi
├── app_nhan.py             # Web người nhận
├── gen_keys.py             # Tạo khóa RSA
├── keys/
│   ├── private.pem
│   └── public.pem
├── templates/
│   ├── index.html
│   ├── room.html
│   ├── verify.html
│   └── show_received.html
└── uploads/
    
```

---

## 🚀 Hướng dẫn chạy

### 1. Cài thư viện

```bash
pip install flask pycryptodome pillow requests
```

### 2. Tạo khóa RSA

```bash
python gen_keys.py
```

### 3. Chạy ứng dụng

- **Máy gửi**: `python app_gui.py` (port `8000`)
- **Máy nhận**: `python app_nhan.py` (port `8001`)

Truy cập:
- Người gửi: http://localhost:8000  
- Người nhận: http://localhost:8001

---

## 📷 Demo giao diện

> _Thêm ảnh minh họa tại đây nếu có_

---

## 📌 Ghi chú

- ✅ Hỗ trợ ảnh từ **upload trực tiếp** hoặc **Google Drive link**
- 🔐 Toàn bộ ảnh được gắn watermark, mã hóa DES, ký RSA, kiểm tra SHA-512
- 🌐 Truyền giữa 2 máy nội bộ (LAN)
- 🔄 Tự động gửi & nhận file  + phản hồi ACK/NACK

---

© 2025 – Bài tập lớn **An toàn bảo mật thông tin**

