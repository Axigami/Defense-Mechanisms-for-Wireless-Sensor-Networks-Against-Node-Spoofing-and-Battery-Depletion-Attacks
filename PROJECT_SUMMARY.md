# Tóm Tắt Dự Án: Cơ Chế Phòng Thủ Cho Mạng Cảm Biến Không Dây (WSN)

## Tong Quan

Dự án này nghiên cứu và triển khai **hệ thống phòng thủ đa tầng (Defense-in-Depth)** bảo vệ mạng cảm biến không dây (WSN) chống lại các cuộc tấn công:
- **Sybil Attack**: Kẻ tấn công tạo ra hàng loạt định danh giả (ID giả mạo)
- **Node Spoofing**: Mạo danh ID của node hợp lệ (Framing Attack)
- **Vampire Attack**: Tấn công cạn kiệt pin năng lượng
- **Distraction Attack**: Tấn công đánh lạc hướng để che giấu sự kiện thật

## Kien Truc He Thong

### 1. Ba Lớp Phòng Thủ Chính (Từ `DEFENSE_SYBIL_SPOOFING.md`)

| Lớp | Tên | Chức Năng |
|-----|-----|-----------|
| **Lớp 1** | Xác Thực Định Danh & Không Gian Sóng | Phát hiện Sybil/Spoofing qua Whitelist + Spatial Map |
| **Lớp 2** | Lọc Dữ Liệu Thống Kê FDI (3-Sigma) | Phát hiện dữ liệu bất thường mềm dẻo (Soft Penalty) |
| **Lớp 3** | Xác Thực Chéo Không Gian (Spatial Consensus) | Phân biệt cháy thật vs giả qua đồng thuận láng giềng 15m |

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

## Cau Truc Thu Muc

```
src/
├── attacks/              # Kịch bản tấn công (vampire_attack/)
├── defense/              # Code phòng thủ C (vampire_defense*.c/h, ACL patch)
├── ml/                   # Pipeline ML: train, export, convert sang C
│   ├── collect_training_data.py
│   ├── train_and_export.py
│   ├── convert_to_c.py
│   └── data/output/      # Dữ liệu huấn luyện & mô hình
├── monitoring/           # Dashboard & Server giám sát (Python/Flask)
│   ├── monitor_server.py       # Giám sát chính
│   ├── ml_monitor_server.py    # Giám sát ML + ACL
│   ├── attacker_server.py      # Server giả lập tấn công
│   └── templates/              # Giao diện web
├── nodes/                # Firmware Contiki-NG (node.c, sink.c)
├── contiki-ng/           # OS Contiki-NG (submodule)
├── data/                 # Kết quả thực nghiệm (CSV)
├── *.csc                 # File mô phỏng Cooja (3 kịch bản)
├── analyze.py            # Phân tích kết quả
└── compare_scenarios.py  # So sánh kịch bản
```

## 3 Kich Ban Thuc Nghiem (Cooja)

| File `.csc` | Loại Tấn Công | Mô Tả |
|-------------|---------------|-------|
| `wsn-2sink-sybil.csc` | **Sybil** | Node 53 spawn ID 100+, báo 85°C giả |
| `wsn-2sink-spoofing.csc` | **Spoofing** | Node 53 mạo danh Node 12 (Framing) |
| `wsn-2sink-distraction.csc` | **Distraction** | ID 200+ báo 25°C che giấu 3 node legit 85°C |
| `wsn-2sink-full-with-vampire.csc` | **Vampire** | Tấn công cạn kiệt năng lượng |

## Diem Ky Thuat Noi Bat

1. **Spatial Map thay vì Temperature History**: Tách biệt "Danh tính khai báo" vs "Vị trí phát sóng thực" → Chống Framing Attack triệt để
2. **Trust Score động**: Hard Drop (<1%) cho kẻ xâm nhập + Soft Penalty (β+2.0) cho nhiễu tự nhiên
3. **Embedded ML**: Decision Tree chạy trực tiếp trên vi điều khiển (không cần cloud)
4. **Human-in-the-loop**: ACL 2 tầng (Auto 80-90% + Manual Review) giảm False Positive
5. **Spatial Consensus (15m)**: Xác nhận sự kiện qua đồng thuận láng giềng

## Cach Chay

```bash
# 1. Huấn luyện ML
cd src/ml && python train_and_export.py

# 2. Chạy mô phỏng Cooja (cần Contiki-NG)
# Mở file .csc trong Cooja Simulator

# 3. Chạy Dashboard giám sát
cd src/monitoring && python monitor_server.py
# Hoặc ML Monitor (có ACL)
cd src/monitoring && python ml_monitor_server.py
```

## Ket Qua Mong Doi

- **Sybil**: ID giả bị Trust <1% và chặn hoàn toàn
- **Spoofing**: Node nạn nhân giữ Trust 91%, gói mạo danh bị hủy
- **Distraction**: ID giả bị khóa, 3 node legit kích hoạt báo cháy chính xác
- **Vampire**: Phát hiện hành vi cạn kiệt pin qua ML nhúng
