# Tài Liệu Đặc Tả Thuật Toán Phòng Thủ WSN (defense.py)

Bản ghi chú này ánh xạ luồng thực thi của tập lệnh `defense.py` từ trên xuống dưới, nhằm mục đích nắm bắt nhanh context logic (Chain of Thoughts) của hệ thống phòng thủ.

## 1. Cấu Trúc Tổng Quan
Hệ thống phòng thủ hoạt động theo mô hình Pipeline, mỗi gói tin đến sẽ đi qua các lớp kiểm tra (Layer) tuần tự. Gói tin bị đánh dấu lỗi ở lớp trước vẫn tiếp tục đi qua lớp sau để đánh giá mức độ vi phạm, nhưng kết quả cuối cùng sẽ được tổng hợp ở module **TrustManager**.

```mermaid
graph TD;
    A[Nhận Gói Tin] --> B[Lớp 1: Kiểm Tra Cú Pháp];
    B --> C[Lớp 2: Quét Tọa Độ (Ghost ID)];
    C --> D[Lớp 3: Bắt Sybil/Spoofing (RSSI)];
    D --> E[Lớp 4: Xác Minh Cháy & Bắt FDI (Không Gian - Thời Gian)];
    E --> F[TrustManager Cập Nhật Điểm];
    F --> G[Cảnh Báo & Chặn (Block)];
```

---

## 2. Chi Tiết Các Lớp (Layers)

### Lớp 1: Cú Pháp và Dữ Liệu
- Hệ thống giải mã gói tin (Regex parse).
- Trích xuất: `Node ID`, `RSSI`, `Nhiệt độ (Temp)`.
- Nếu gói tin hỏng hoặc là bản tin Routing (như DIS, DIO), hệ thống bỏ qua bước quét và chỉ ghi log định tuyến.

### Lớp 2: Kiểm Tra Không Gian Tọa Độ (Ghost ID)
- Hàm `load_topology_map()` được gọi lúc khởi tạo để nạp tọa độ `(X, Y)` thực tế của các Node từ file `.csc` của Cooja.
- Khi một gói tin đến, hệ thống đối chiếu ID:
  - Nếu `Node ID` không tồn tại trong Topology $\rightarrow$ Kẻ tấn công tạo ra ID ma (Ghost ID) để spam mạng.
  - **Hành động:** Đánh dấu `is_fake_id = True` (Sẽ bị Instakill ở TrustManager).

### Lớp 3: Sybil Detector (Bảo Vệ Tính Định Danh Bằng Sóng Vô Tuyến)
**Giai đoạn Học (250 gói tin đầu):**
- Hệ thống im lặng ghi nhận RSSI của từng Node (ở trạng thái bình thường).
- Sau 250 gói, tính toán `Baseline RSSI` (RSSI trung bình) cho mỗi ID.

**Giai đoạn Hoạt Động (Sau 250 gói):**
- `SybilDetector.check()`: Đối chiếu RSSI của gói tin hiện tại với `Baseline RSSI`.
- **Nếu lệch > 3.0 dBm:** Kẻ tấn công đứng ở vị trí khác nhưng mạo danh ID này $\rightarrow$ **RSSI MISMATCH**. Đánh dấu `sybil_passed = False`.
- **Hành động phụ (Bẫy Vùng Đen):** Nếu một vị trí liên tục phát ra nhiều ID khác nhau, vị trí đó bị đưa vào `Blacklisted Zone`. Bất kỳ ID nào phát ra từ vùng RSSI đó đều bị chặn.

### Lớp 4: Fire Confirmation Protocol (Xác Minh Cháy Thực / Bắt FDI)
Đây là lớp quan trọng nhất (Spatio-Temporal Detection). Nó chỉ kích hoạt khi `Temp > 60.0°C`. 

**1. Khóa Mõm (Observation Window = 6 giây)**
- Ghi nhận `fire_timestamps[node_id]`.
- Khi `elapsed < 6.0s`: Hệ thống ở trạng thái 🔍 **OBSERVING**. Nó tạm thời giả định `fdi_passed = True` để thu thập dữ liệu hàng xóm mà không vội vàng phán xét.

**2. Đóng Cửa Sổ Phán Xét (Giây thứ 6 trở đi)**
Khi `elapsed >= 6.0s`, hệ thống lôi toàn bộ dữ liệu ra đối chiếu:

- **Loại trừ Nhân chứng Tử thần (Blacklist Witness Exclusion):**
  - Khi quét tìm các hàng xóm lân cận trong bán kính 15m (`hot_neighbors`), bất kỳ node nào đã bị cách ly vào Blacklist (`is_blacklisted(nid) == True`) sẽ bị **loại bỏ ngay lập tức**. Node đã chết không thể làm chứng cho node sống.

- **Quét Bẫy Không Gian (Teleporting Fire):**
  - Quét TOÀN MẠNG LƯỚI. Nếu 2 Node bùng phát nhiệt độ lệch nhau `< 5 giây`, nhưng cách nhau `> 35 mét`.
  - $\rightarrow$ Logic vật lý: Lửa không nhảy cóc 35m trong 5s.
  - $\rightarrow$ **HIJACK DETECTED: Teleporting Fire**.

- **Quét Bẫy Thời Gian (Sync Burst):**
  - Quét 15 mét xung quanh. Nếu có $\ge 4$ hàng xóm cùng bùng phát nhiệt độ (lệch nhau `< 5 giây`).
  - $\rightarrow$ Logic vật lý: Lửa lan truyền cần thời gian, không thể có 5 cảm biến cùng nóng lên chạm 85°C cùng một mili-giây.
  - $\rightarrow$ **HIJACK DETECTED: Sync Burst**.

- **Quét Bẫy Vách Đá Nhiệt Độ (Temp Cliff):**
  - Nếu trong cụm 15m có $\ge 5$ node nóng, nhưng ở vành đai ngoài (15m–25m) lại có $\ge 2$ node lạnh ngắt ($< 40^\circ\text{C}$).
  - $\rightarrow$ Logic vật lý: Đám cháy lớn phải có vùng chuyển tiếp nhiệt (gradient), không thể tồn tại ranh giới cắt đột ngột.
  - $\rightarrow$ **HIJACK DETECTED: Temp Cliff**.

- **Nhận Diện Làn Sóng Tấn Công & Bắt Thông Đồng (Attack Wave Awareness & Collusion Detection):**
  - Khi kẻ tấn công gửi gói tin ồ ạt làm nghẽn sóng vô tuyến (CSMA/CA contention), các gói tin bị delay lệch nhau > 5s và các node bị chiếm quyền gần nhau (< 15m) sẽ cố tình **bảo lãnh chéo (Mutual Vouching)** cho nhau.
  - **Cơ chế phòng thủ thích ứng:**
    1. Hệ thống đếm số lượng node bị tử hình vì `HIJACK` trong vòng 120 giây gần nhất (`recent_hijack_blocks`).
    2. Nếu $\ge 3$ node bị chặn vì `HIJACK` $\rightarrow$ Tự động kích hoạt trạng thái **ATTACK WAVE** (Làn sóng tấn công đang diễn ra).
    3. Trong trạng thái này, điều kiện để được công nhận `TRUE FIRE` đòi hỏi **tư cách nhân chứng độc lập (Witness Credibility)**: Phải có ít nhất 1 hàng xóm nóng là node "trong sạch" (`fire_warning_count == 0`, không nằm trong diện nghi vấn của hệ thống).
    4. Nếu TẤT CẢ các hàng xóm làm chứng đều là nghi phạm đang bị theo dõi $\rightarrow$ **COLLUSION DETECTED: Mutual Vouching** $\rightarrow$ **INSTANT BLOCK!**
  - **Bảo toàn kịch bản Cháy thật (Distraction):** Trong kịch bản cháy thật, các node tấn công chỉ bị chặn với tội danh `SPOOF/SYBIL` (ID ma), số lượng node bị chặn vì `HIJACK` luôn bằng 0. Do đó, trạng thái Attack Wave **không bao giờ kích hoạt nhầm**, các node cháy thật vẫn bảo lãnh cho nhau hoàn toàn bình thường.

- **Cháy Thực (True Fire):**
  - Nếu không dính các bẫy trên, mạng không trong trạng thái Attack Wave (hoặc có nhân chứng hợp lệ), và có từ 1 hàng xóm trở lên (trong 15m) cũng báo nhiệt độ cao.
  - $\rightarrow$ **TRUE FIRE CONFIRMED**. Gradient nhiệt lan truyền tự nhiên, duy trì 100% Trust.

- **Báo Cáo Lá Láo (Cô lập):**
  - Đứng trơ trọi một mình báo cháy >60°C sau 6 giây mà không hàng xóm nào bị.
  - $\rightarrow$ **HIJACK DETECTED: Lone Node Anomaly**.

---

## 3. Quản Lý Niềm Tin (TrustManager)
Bất kể các lớp trên đưa ra kết luận gì, quyền sinh sát thuộc về hệ thống Điểm Tin Cậy (dựa trên mô hình Beta Distribution `Alpha/Beta`).

- **Điểm cơ bản:** Khởi đầu ở mức 90.9%. Nếu `Trust Score < 40%` $\rightarrow$ **BLACKLIST** (Cô lập vĩnh viễn khỏi mạng lưới).
- **Hành vi tốt:** Nếu qua cả Sybil và FDI $\rightarrow$ Cộng điểm `Alpha` (tăng độ uy tín).
- **Trảm Lập Quyết (Instant Kill):**
  - `attack_type == "HIJACK"`: Các Node báo dữ liệu cháy giả mạo (FDI đồng loạt, Collusion bảo lãnh chéo).
  - `attack_type in ["ZONE_BLOCK", "SYBIL_CLONE"]`: Kẻ tấn công Sybil mạo danh ID.
  - $\rightarrow$ **Cộng 100 điểm Beta (Tử hình ngay lập tức, đưa Trust Score về ~1%)**.
- **Trừ Từ Từ:**
  - `RSSI MISMATCH`: Sai số sóng vô tuyến nhẹ (Cộng 4 điểm Beta).
  - Lỗi FDI nhẹ (Không xác định rõ Hijack): Cộng 2 điểm Beta.

---
**Kết luận:** Nhờ chuỗi Chain of Thoughts này, hệ thống `defense.py` hoàn toàn KHÔNG THỂ BỊ BIAS (thiên vị). Nó chỉ dựa vào công thức Toán học Không gian `(X, Y)`, công thức Khoảng cách thời gian `< 5s`, trạng thái làn sóng tấn công thích ứng (Attack Wave Awareness), và công thức sóng vô tuyến `dBm`. Con người không thể lừa được các nguyên lý Vật lý này.
