from flask import Flask, render_template, request, redirect, url_for, session, send_file
from Crypto.Cipher import DES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA512
from PIL import Image, ImageDraw, ImageFont
import requests  
from urllib.parse import urlparse, parse_qs
from flask import jsonify
import os, base64, time, hashlib, zipfile, io


app = Flask(__name__)
app.secret_key = 'supersecretkey'

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Thêm watermark vào ảnh
def add_watermark(image_stream, watermark_text):
    image = Image.open(image_stream).convert("RGBA")
    txt_layer = Image.new('RGBA', image.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)

    font_size = max(20, image.width // 20)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()

    # Sửa lỗi textsize bằng getbbox
    bbox = font.getbbox(watermark_text)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Lặp watermark phủ toàn ảnh
    x_spacing = text_width + 400
    y_spacing = text_height + 300

    for y in range(0, image.height, y_spacing):
        for x in range(0, image.width, x_spacing):
            draw.text((x, y), watermark_text, fill=(255, 255, 255, 80), font=font)

    watermarked = Image.alpha_composite(image, txt_layer).convert("RGB")
    buffer = io.BytesIO()
    watermarked.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.read()



# Padding cho DES
def pad(data):
    while len(data) % 8 != 0:
        data += b' '
    return data

# Mã hóa DES
def encrypt_des(data, key, iv):
    cipher = DES.new(key, DES.MODE_CBC, iv)
    return cipher.encrypt(pad(data))

# Ký metadata bằng private key
def sign_metadata(metadata):
    private_key = RSA.import_key(open("keys/private.pem").read())
    h = SHA512.new(metadata)
    return pkcs1_15.new(private_key).sign(h)



@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get('image')
        drive_link = request.form.get('drive_link')
        watermark = request.form['watermark']
        filename = None
        image_stream = None

        if drive_link:  # Ưu tiên xử lý link trước
            try:
                from urllib.parse import urlparse, parse_qs
                # Lấy ID từ link Drive
                if "id=" in drive_link:
                    file_id = parse_qs(urlparse(drive_link).query).get("id", [None])[0]
                else:
                    parts = drive_link.split('/')
                    file_id = parts[parts.index("d") + 1] if "d" in parts else None

                if not file_id:
                    return "❌ Link Google Drive không hợp lệ!"

                # Link tải ảnh
                download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                response = requests.get(download_url)
                if response.status_code != 200:
                    return "❌ Không thể tải ảnh từ Google Drive!"

                image_stream = io.BytesIO(response.content)
                filename = os.path.join(UPLOAD_FOLDER, f"drive_image_{int(time.time())}.png")

            except Exception as e:
                return f"❌ Lỗi khi tải ảnh từ Drive: {e}"

        elif file and file.filename != "":
            filename = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filename)
            image_stream = file.stream

        else:
            return "❌ Bạn cần upload ảnh hoặc dán link từ Google Drive."

        # Thêm watermark
        img_data = add_watermark(image_stream, watermark)

        # Mã hóa ảnh
        session_key = os.urandom(8)
        iv = os.urandom(8)
        ciphertext = encrypt_des(img_data, session_key, iv)
        hash_val = hashlib.sha512(iv + ciphertext).hexdigest()
        metadata = (os.path.basename(filename) + str(int(time.time())) + watermark).encode()
        signature = sign_metadata(metadata)

        # Mã hóa khóa phiên
        receiver_pubkey = RSA.import_key(open("keys/public.pem").read())
        cipher_rsa = PKCS1_v1_5.new(receiver_pubkey)
        encrypted_session_key = cipher_rsa.encrypt(session_key)

        # Tạo file ZIP
        zip_path = os.path.join(UPLOAD_FOLDER, "output.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            zipf.writestr("cipher.des", ciphertext)
            zipf.writestr("iv.txt", iv)
            zipf.writestr("signature.sig", signature)
            zipf.writestr("hash.txt", hash_val)
            zipf.writestr("metadata.txt", metadata)
            zipf.writestr("session_key_rsa.bin", encrypted_session_key)

        return render_template("index.html", filename="cipher.des", zipname="output.zip")

    return render_template("index.html")


@app.route('/handshake', methods=['POST'])
def handshake():
    message = request.form.get('message')
    if message == "Hello!":
        return "Ready!", 200
    return "Invalid message", 400

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if not session.get('room_access'):
        return redirect(url_for('room'))

    result = None
    image_data = None

    if request.method == 'POST':
        # Nếu bấm nút Xóa ảnh
        if request.form.get('delete_image'):
            return render_template("Verify.html", result=None, image_data=None)

        file = request.files.get('zipfile')
        callback_url = request.form.get('callback_url')  # Lấy callback_url từ form nếu có

        if file:
            zip_bytes = file.read()
            try:
                with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as z:
                    cipher_data = z.read('cipher.des')
                    iv = z.read('iv.txt')
                    sig = z.read('signature.sig')
                    hash_txt = z.read('hash.txt').decode()
                    metadata = z.read('metadata.txt')
                    encrypted_session_key = z.read('session_key_rsa.bin')

                # Kiểm tra hash
                current_hash = hashlib.sha512(iv + cipher_data).hexdigest()
                if current_hash != hash_txt:
                    result = "❌ Ảnh đã bị chỉnh sửa – hash không khớp!"
                else:
                    # Kiểm tra chữ ký
                    public_key = RSA.import_key(open("keys/public.pem").read())
                    h = SHA512.new(metadata)
                    try:
                        pkcs1_15.new(public_key).verify(h, sig)

                        # Giải mã session key bằng private key
                        private_key = RSA.import_key(open("keys/private.pem").read())
                        cipher_rsa = PKCS1_v1_5.new(private_key)
                        session_key = cipher_rsa.decrypt(encrypted_session_key, None)

                        if not session_key or len(session_key) != 8:
                            result = "❌ Không giải mã được khóa phiên!"
                        else:
                            # Giải mã ảnh
                            cipher = DES.new(session_key, DES.MODE_CBC, iv)
                            plaintext = cipher.decrypt(cipher_data).rstrip(b' ')
                            if plaintext[:4] == b'\x89PNG':
                                mime = "image/png"
                            else:
                                mime = "image/jpeg"
                            image_data = f"data:{mime};base64," + base64.b64encode(plaintext).decode()
                            result = "✅ Ảnh hợp lệ – chữ ký và hash đều đúng!"
                    except (ValueError, TypeError):
                        result = "❌ Chữ ký không hợp lệ!"
            except Exception as e:
                result = f"Lỗi khi xử lý file: {e}"

            # ✅ Gửi phản hồi ACK/NACK nếu có callback_url
            if callback_url:
                try:
                    if result.startswith("✅"):
                        requests.post(callback_url, data={
                            "status": "ACK",
                            "message": "Ảnh hợp lệ. Chữ ký và hash đều đúng."
                        })
                    else:
                        requests.post(callback_url, data={
                            "status": "NACK",
                            "message": result
                        })
                except Exception as e:
                    print(f"[⚠️] Không thể gửi phản hồi về người gửi: {e}")

    return render_template("Verify.html", result=result, image_data=image_data)


@app.route('/download/<filename>')
def download_file(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return f"File {filename} không tồn tại", 404



@app.route('/room', methods=['GET', 'POST'])
def room():
    if request.method == 'POST':
        password = request.form['room_pass']
        if password == '123456':  # Kiểm tra mã phòng
            session['room_access'] = True
            return redirect(url_for('verify'))  # Chuyển hướng đến trang xác minh
        else:
            return render_template('room.html', error="🚫 Sai mã phòng!")
    return render_template('room.html')

@app.route('/logout')
def logout():
    session.pop('room_access', None)
    return redirect(url_for('room'))



@app.route('/delete/<filename>')
def delete_file(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return redirect(url_for('index'))  # Quay lại trang chính sau khi xóa
    return f"File {filename} không tồn tại", 404


@app.route('/send_file', methods=['POST'])
def send_file_to_another_machine():
    file = request.files['file']
    target_ip = request.form['target_ip']
    callback_ip = request.form['callback_ip']

    target_url = f'http://{target_ip}:8001/receive_file'
    callback_url = f'http://{callback_ip}:8000/ack_handler'

    if file:
        try:
            response = requests.post(
                target_url,
                files={'file': (file.filename, file.stream, file.mimetype)},
                data={'callback_url': callback_url},
                timeout=5
            )

            data = response.json()
            if response.status_code == 200 and data.get('status') == 'success':
                return f'''
                    <h2>✅ {data.get("message")}</h2>
                    <a href="{data.get("file_url")}" target="_blank">📁 Xem file tại máy nhận</a>
                    <p>⏳ Chờ phản hồi xác minh từ máy nhận...</p>
                '''
            else:
                return f"❌ Gửi thất bại: {data.get('message')}", response.status_code

        except Exception as e:
            return f"❌ Phản hồi không hợp lệ: {str(e)}", 500

    return "❌ Không có file nào được tải lên", 400

@app.route('/ack_handler', methods=['POST'])
def ack_handler():
    print("📥 Đã vào route /ack_handler")  # 👈 in dòng này trước
    print("🔥 Đã nhận phản hồi từ máy nhận")
    status = request.form.get("status")
    message = request.form.get("message")
    print(f"📩 {status} – {message}")
    return "OK", 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
