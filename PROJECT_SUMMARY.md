# Tóm Tắt Dự Án: Cơ Chế Phòng Thủ Cho Mạng Cảm Biến Không Dây (WSN)

## Tổng Quan

Dự án này nghiên cứu và triển khai **hệ thống phòng thủ đa tầng (Defense-in-Depth)** bảo vệ mạng cảm biến không dây (WSN) chống lại các cuộc tấn công:
- **Sybil Attack**: Kẻ tấn công tạo ra hàng loạt định danh giả (ID giả mạo) phát tán dữ liệu sai lệch
- **Hijacked Node & False Data Injection (FDI)**: Chiếm quyền điều khiển các node hợp lệ để bơm dữ liệu báo cháy giả đồng loạt
- **Distraction Attack**: Tấn công đánh lạc hướng (bơm dữ liệu nhiệt độ bình thường từ ID giả) nhằm che giấu sự kiện cháy thật
- **Vampire Attack**: Tấn công làm cạn kiệt năng lượng pin ở tầng định tuyến RPL

## Kiến Trúc Hệ Thống

### 1. Kiến Trúc Phòng Thủ 4 Lớp Chống Sybil, Spoofing & FDI (Từ `defense_logic.md` & `defense_presentation_guide.md`)

| Lớp | Tên | Chức Năng |
|-----|-----|-----------|
| **Lớp 1** | Bóc Tách Cú Pháp & Tiền Xử Lý (Parser & Sanitizer) | Giải mã dữ liệu cảm biến (`Node ID`, `RSSI`, `Temp`, `Timestamp`) và tách biệt bản tin điều khiển RPL |
| **Lớp 2** | Đối Chiếu Không Gian Tọa Độ (Ghost ID Detection) | Đối chiếu danh tính với bản đồ vật lý (`TopologyMap`), chặn tức thì các định danh không tồn tại |
| **Lớp 3** | Dấu Vân Tay Sóng Vô Tuyến (Physical RSSI Fingerprinting) | Phát hiện mạo danh qua độ lệch `Baseline RSSI` (> 3.0 dBm) và khóa vùng phát sóng (`Zone Block`) |
| **Lớp 4** | Giao Thức Xác Minh Cháy Không Gian - Thời Gian (Spatio-Temporal Protocol) | Phân biệt cháy thật và báo động giả FDI qua bẫy vật lý tức thời, cửa sổ quan sát 10s, đồng thuận láng giềng 15m và chống thông đồng (`Attack Wave Awareness`) |
| **TrustManager** | Quản Lý Điểm Tin Cậy (Mô Hình Phân Phối Beta) | Đánh giá điểm tin cậy động (`Alpha/Beta`), đóng băng điểm khi quan sát và cô lập vĩnh viễn khi `Trust Score < 40%` |

### 2. Cơ Chế ACL & ML Nhúng (Từ `ACL_SUMMARY.md`)

```
[Gói tin RPL] → [Node: Feature Extraction] → [Embedded ML: Decision Tree]
                                                    ↓
                                          [Phát ML_ALERT]
                                                    ↓
                                    [ACL Monitor: 2 Tầng]
                                    ├── Tầng 1: Auto-Approve (ngưỡng cứng)
                                    └── Tầng 2: Human Review (Pending UI)
                                                    ↓
                                    [Enforcement: Blacklist + Drop]
```

**5 đặc trưng ML tại node:**
- `dio_rate`, `version_delta`, `rank`, `rank_delta`, `is_poison`

**Ngưỡng Auto-Approve:**
- `consecutive_alerts >= 3`, `dio_rate >= 40`, `rank_delta >= 400`
- `version_delta >= 5`, `≥2 node cùng báo 1 đối tượng`

## Cấu Trúc Thư Mục

```
src/
├── attacks/              # Kịch bản mô phỏng tấn công (.csc & vampire_attack/)
│   ├── wsn-2sink-sybil.csc
│   ├── wsn-2sink-hijacked.csc
│   ├── wsn-2sink-distraction.csc
│   ├── wsn-vampire-attack.csc
│   └── vampire_attack/
├── defense/              # Hệ thống phòng thủ Python & C
│   ├── defense.py        # Pipeline 4 lớp chống Sybil/Spoofing/FDI & TrustManager
│   └── vampire_defense*.c/h, rpl_acl_integration.patch
├── ml/                   # Pipeline ML: train, export, convert sang C
│   ├── collect_training_data.py
│   ├── train_and_export.py
│   ├── convert_to_c.py
│   └── data/output/      # Dữ liệu huấn luyện & mô hình
├── monitoring/           # Dashboard & Server giám sát (Python/Flask)
│   ├── monitor_server.py       # Giám sát chính & tích hợp DefenseSystem
│   ├── ml_monitor_server.py    # Giám sát ML + ACL
│   ├── attacker_server.py      # Server điều khiển kịch bản tấn công (C&C)
│   └── templates/              # Giao diện web (dashboard.html, attacker.html, ...)
├── nodes/                # Firmware Contiki-NG (node.c, sink.c, sybil_node.c, hijacked_node.c, ...)
├── data/                 # Dữ liệu log mô phỏng (logs/) và kết quả phân tích (results/)
├── analyze.py            # Phân tích định lượng kết quả mô phỏng & xuất biểu đồ
└── compare_scenarios.py  # So sánh các kịch bản thực nghiệm
```

## Các Kịch Bản Thực Nghiệm (Cooja)

| File `.csc` | Loại Tấn Công | Mô Tả |
|-------------|---------------|-------|
| `wsn-2sink-sybil.csc` | **Sybil & FDI** | Node 53 phát sinh đa định danh giả (ID 100–110) kèm dữ liệu nhiệt độ giả 85°C |
| `wsn-2sink-hijacked.csc` | **Hijacked Node (FDI)** | 15 node hợp lệ bị chiếm quyền (Node 2–16) phát tán dữ liệu báo cháy giả 85°C |
| `wsn-2sink-distraction.csc` | **Distraction & True Fire** | Node 54 phát ID giả (200+) báo 25°C nhằm đánh lạc hướng khi cụm Node 30, 31, 32 cháy thật (85°C) |
| `wsn-2sink-full-with-vampire.csc` | **Vampire** | Tấn công cạn kiệt năng lượng |

## Điểm Kỹ Thuật Nổi Bật

1. **Đối chiếu Không gian Tọa độ & Dấu vân tay Sóng vô tuyến (`Spatial Map & RSSI Profiling`)**: Tách biệt danh tính khai báo với vị trí vật lý thực tế, ngăn chặn triệt để tấn công giả mạo đa định danh (Sybil) và khóa vùng phát sóng độc hại (`Zone Block`).
2. **Giao thức Xác minh Cháy Không gian - Thời gian & Điểm Tin cậy động (`Beta Trust Model`)**: Kết hợp cửa sổ quan sát 10s (đóng băng điểm tin cậy), xác thực chéo láng giềng 15m và nhận diện làn sóng tấn công (`Attack Wave Awareness`) để phân biệt chính xác 100% giữa cháy thật và báo động giả FDI.
3. **Embedded ML**: Decision Tree chạy trực tiếp trên vi điều khiển (không cần cloud)
4. **Human-in-the-loop**: ACL 2 tầng (Auto 80-90% + Manual Review) giảm False Positive

## Hướng Dẫn Thực Thi

```bash
# 1. Huấn luyện mô hình ML (nếu cần)
cd src/ml && python train_and_export.py && python convert_to_c.py

# 2. Chạy mô phỏng trong Cooja
# Mở file .csc tương ứng trong Cooja Simulator

# 3. Khởi động Dashboard giám sát
cd src/monitoring && python monitor_server.py ../data/logs/run_1.log
# Hoặc ML Monitor (có ACL)
cd src/monitoring && python ml_monitor_server.py
```

## Kết Quả Thực Nghiệm

- **Sybil**: Các định danh giả (Ghost ID) bị hạ điểm tin cậy xuống `< 1%`, bị đưa vào danh sách đen (`Blacklist`) và khóa vùng phát sóng (`Zone Block`) ngay từ gói tin đầu tiên.
- **Hijacked Node (Coordinated FDI)**: Các node hợp lệ bị chiếm quyền báo cháy giả bị phát hiện qua bẫy không gian - thời gian (`Teleporting Fire`, `Lone Node Anomaly`, `Collusion Detection`) và bị cô lập hoàn toàn.
- **Distraction**: Các gói tin nghi binh bị chặn tại Lớp 2 & Lớp 3, trong khi cụm 3 node cháy thật (Node 30, 31, 32) được xác nhận chính xác (`TRUE FIRE CONFIRMED`) với độ tin cậy duy trì 100%.
- **Vampire**: Phát hiện hành vi cạn kiệt pin qua ML nhúng
