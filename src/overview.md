# TỔNG QUAN DỰ ÁN - Mạng Cảm Biến Không Dây (WSN)

## 1. CẤU HÌNH MẠNG HIỆN TẠI

### Cấu trúc
- **52 nodes**: 2 Sinks (ID: 1, 27) + 50 Sensors (ID: 2-26, 28-52)
- **2 Clusters**: Cluster 1 (nodes 1-26), Cluster 2 (nodes 27-52)
- **Protocol**: RPL Lite + TSCH MAC + UDP
- **Radio**: Phạm vi 50 đơn vị, công suất 0 dBm
- **Năng lượng**: 7200 mJ/node ban đầu
- **Ứng dụng**: Gửi 16 bytes mỗi 60 giây

### Kết quả Baseline
```
Nodes hoạt động:    50/50
PDR:                99.88%
Thời gian:          314.8 giờ
Dead nodes:         6 (hết pin tự nhiên)
Throughput:         0.097923 bps
```

---

## 2. CÁC KÝ HIỆU TRONG RUN.LOG

### 2.1 GEN - Tạo dữ liệu
```
60342000 ID:31 [INFO: NODE] GEN cluster=2 node=31 gen_count=1
```
| Trường | Ý nghĩa | Giá trị ví dụ |
|--------|---------|---------------|
| `60342000` | Timestamp Cooja (ms) | 60342000 ms = 60.3s |
| `ID:31` | Node ID | Node 31 |
| `cluster` | Cụm thuộc về | 2 |
| `node` | ID node | 31 |
| `gen_count` | Số lần đã tạo data | 1 |

**Ý nghĩa**: Sensor tạo dữ liệu mới để gửi đi

---

### 2.2 TX - Truyền gói tin
```
61360520 ID:31 [INFO: NODE] TX cluster=2 node=31 seq=0 energy_mj=7072 bytes=16
```
| Trường | Ý nghĩa | Giá trị ví dụ |
|--------|---------|---------------|
| `cluster` | Cụm | 2 |
| `node` | Node gửi | 31 |
| `seq` | Số thứ tự gói tin | 0 |
| `energy_mj` | Năng lượng còn lại (mJ) | 7072 mJ |
| `bytes` | Kích thước gói | 16 bytes |

**Ý nghĩa**: Sensor gửi gói tin đi

---

### 2.3 RX - Nhận tại Sink
```
61360520 ID:27 [INFO: SINK] RX sink=27 cluster=2 node=50 seq=0 energy_mj=7061 bytes=16 latency_ms=95
```
| Trường | Ý nghĩa | Giá trị ví dụ |
|--------|---------|---------------|
| `sink` | Sink nào nhận | 27 |
| `cluster` | Cụm nguồn | 2 |
| `node` | Node nguồn | 50 |
| `seq` | Số thứ tự | 0 |
| `energy_mj` | Năng lượng node nguồn | 7061 mJ |
| `bytes` | Kích thước nhận | 16 bytes |
| `latency_ms` | Độ trễ end-to-end | 95 ms |

**Ý nghĩa**: Sink nhận thành công gói tin từ sensor

---

### 2.4 DEAD - Node chết
```
157743000 ID:52 [INFO: NODE] DEAD cluster=2 node=52 time_alive_s=157 last_seq=0 total_gen=1 total_sent=0
```
| Trường | Ý nghĩa | Giá trị ví dụ |
|--------|---------|---------------|
| `cluster` | Cụm | 2 |
| `node` | Node chết | 52 |
| `time_alive_s` | Thời gian sống (giây) | 157s |
| `last_seq` | Seq cuối cùng gửi | 0 |
| `total_gen` | Tổng data đã tạo | 1 |
| `total_sent` | Tổng gói đã gửi | 0 |

**Ý nghĩa**: Node hết pin (energy = 0)

---

### 2.5 STATUS - Báo cáo định kỳ
```
300000000 ID:15 [INFO: NODE] STATUS node=15 energy_mj=7050 duty_pct=8 rank=512
```
| Trường | Ý nghĩa | Giá trị ví dụ |
|--------|---------|---------------|
| `node` | Node ID | 15 |
| `energy_mj` | Năng lượng còn lại | 7050 mJ |
| `duty_pct` | Radio duty cycle (%) | 8% |
| `rank` | RPL rank (khoảng cách đến sink) | 512 |

**Ý nghĩa**: Node báo cáo tình trạng (mỗi 5 phút)

---

### 2.6 TXFAIL - Truyền thất bại
```
120000000 ID:45 [INFO: NODE] TXFAIL cluster=2 node=45 gen_count=2
```
| Trường | Ý nghĩa | Giá trị ví dụ |
|--------|---------|---------------|
| `cluster` | Cụm | 2 |
| `node` | Node thất bại | 45 |
| `gen_count` | Data đã tạo nhưng chưa gửi được | 2 |

**Ý nghĩa**: Không tìm được đường đi hoặc chưa có parent (RPL chưa associate)

---

## 3. CÁC CHỈ SỐ TÍNH TỪ LOG

### 3.1 Bảng 15 chỉ số đầy đủ

| STT | Chỉ số | Cách tính từ log | Đơn vị |
|-----|--------|------------------|--------|
| 1 | **Energy Consumed** | `7200 - energy_mj` (từ STATUS/DEAD) | J |
| 2 | **Radio Duty Cycle** | `duty_pct` (từ STATUS) | % |
| 3 | **Time to Node Death** | `time_alive_s` (từ DEAD) | s |
| 4 | **FND / HND / LND** | Node thứ 1/50%/cuối chết (từ DEAD) | s |
| 5 | **Total TX Bytes** | Đếm TX events × `bytes` | Bytes |
| 6 | **Total RX Bytes** | Đếm RX events × `bytes` | Bytes |
| 7 | **Packets Sent** | Đếm TX events mỗi node | packets |
| 8 | **Packets Received** | Đếm RX events tại Sink | packets |
| 9 | **PDR** | `(RX count / TX count) × 100` | % |
| 10 | **Throughput** | `(RX bytes × 8) / thời_gian` | bps |
| 11 | **Data Generation Rate** | `(gen_count × 16 × 8) / thời_gian` | bps |
| 12 | **Latency** | `latency_ms` (từ RX) | ms |
| 13 | **Average Rank** | Trung bình `rank` (từ STATUS) | RPL rank |
| 14 | **Parent Switches** | Đếm số lần `rank` thay đổi đột ngột | lần |
| 15 | **Energy Efficiency** | `RX bytes / Energy consumed` | bytes/J |

### 3.2 4 chỉ số quan trọng nhất

| STT | Chỉ số | Công thức | Events dùng |
|-----|--------|-----------|-------------|
| 1 | **Data truyền được trước khi hết pin** | Tổng RX bytes từ node đó | RX + DEAD |
| 2 | **Throughput Sensor → Sink** | `(RX bytes × 8) / sim_time` | RX |
| 3 | **Tốc độ tạo data** | `(gen_count × 16 × 8) / sim_time` | GEN |
| 4 | **Hiệu quả năng lượng** | `RX bytes / (7200 - energy_mj) × 1000` | RX + STATUS |

---

## 4. VÍ DỤ PHÂN TÍCH MỘT NODE

### Node 31 trong log:
```
60342000 ID:31 [INFO: NODE] GEN cluster=2 node=31 gen_count=1
61360520 ID:31 [INFO: NODE] TX cluster=2 node=31 seq=0 energy_mj=7072 bytes=16
61360520 ID:27 [INFO: SINK] RX sink=27 cluster=2 node=31 seq=0 energy_mj=7072 bytes=16 latency_ms=95
300000000 ID:31 [INFO: NODE] STATUS node=31 energy_mj=7050 duty_pct=8 rank=512
```

### Tính toán:
- **Packets sent**: 1 (có 1 TX event)
- **Packets received**: 1 (có 1 RX event tương ứng)
- **PDR**: 1/1 × 100 = 100%
- **Latency**: 95 ms
- **Energy consumed**: 7200 - 7050 = 150 mJ = 0.15 J
- **Data truyền được**: 16 bytes
- **Hiệu quả năng lượng**: 16 / 0.15 = 106.67 bytes/J
- **Duty cycle**: 8%
- **Rank**: 512 (cách sink khoảng 2 hops)

---

## 5. TẤN CÔNG & PHÒNG THỦ - CODE MẪU

### 5.1 Blackhole Attack - Node nuốt gói tin
```c
// Thêm vào node.c
#define ATTACK_BLACKHOLE 1
#define ATTACKER_NODE_ID 20

static void udp_rx_callback(...) {
    if(node_id == ATTACKER_NODE_ID) {
        LOG_INFO("BLACKHOLE node=%u BỎ packet\n", node_id);
        return; // Không forward
    }
    // Forward bình thường
}
```
**Log sẽ thấy**: TX tăng, RX giảm → PDR giảm mạnh

---

### 5.2 Vampire Attack - Tạo vòng lặp routing
```c
#define ATTACK_VAMPIRE 1
static uint8_t vampire_count = 0;

static void vampire_loop_packet(const uint8_t *data) {
    if(vampire_count < 5) {
        vampire_count++;
        // Gửi lại về node trước
        simple_udp_sendto(&udp_conn, data, 16, &previous_hop);
        LOG_INFO("VAMPIRE loop=%u\n", vampire_count);
    }
}
```
**Log sẽ thấy**: TX events tăng đột biến, energy giảm nhanh → time_alive_s giảm

---

### 5.3 Sinkhole Attack - Hút traffic
```c
#define ATTACK_SINKHOLE 1

static void sinkhole_advertise(void) {
    if(node_id == 25) {
        curr_instance.dag.rank = 128; // Rank giả thấp
        LOG_INFO("SINKHOLE rank=%u\n", curr_instance.dag.rank);
    }
}
```
**Log sẽ thấy**: Các nodes khác có rank thay đổi hướng về node 25, parent_switches tăng

---

### 5.4 Trust-based Defense - Phòng thủ dựa độ tin cậy
```c
typedef struct {
    uint16_t neighbor_id;
    uint8_t trust_score; // 0-100
} trust_entry_t;

static void update_trust(uint16_t neighbor, uint8_t forwarded) {
    if(forwarded) trust_score += 5;
    else trust_score -= 10;
    LOG_INFO("TRUST neighbor=%u score=%u\n", neighbor, trust_score);
}
```
**Log sẽ thấy**: TRUST events mới, blackhole nodes có score thấp, bị tránh

---

### 5.5 Watchdog Defense - Giám sát forwarding
```c
static void watchdog_monitor(uint16_t seq, uint16_t next_hop) {
    // Ghi nhớ packet đã gửi
    LOG_INFO("WATCHDOG giám_sát seq=%u qua=%u\n", seq, next_hop);
}

static void watchdog_timeout_check(void) {
    if(packet_not_forwarded) {
        LOG_INFO("⚠️ WATCHDOG PHÁT_HIỆN node=%u BỎ packet\n", next_hop);
    }
}
```
**Log sẽ thấy**: WATCHDOG events, phát hiện được nodes bỏ packets

---

## 6. SO SÁNH BASELINE VS ATTACK

### Baseline (Bình thường)
```
PDR:                    99.88%
Nodes chết:             6
Thời gian sống TB:      1183s
Energy efficiency:      99.1 bytes/J
Throughput:             0.097923 bps
```

### Blackhole Attack (Node 20)
```
PDR:                    ~60-70% (giảm mạnh)
Nodes chết:             6
TX events:              tương tự
RX events:              giảm ~30-40%
Energy:                 lãng phí do gửi vào hố đen
```

### Vampire Attack (Cluster 1)
```
PDR:                    ~95% (giảm ít)
Nodes chết:             15-20 (tăng nhiều)
Thời gian sống:         500-700s (giảm mạnh)
Energy efficiency:      30-50 bytes/J (giảm mạnh)
TX events:              tăng 3-5× (vòng lặp)
```

### Sinkhole Attack (Node 25)
```
PDR:                    70-80% (giảm vừa)
Parent switches:        50-100× (tăng mạnh)
Rank changes:           liên tục thay đổi
Nodes route qua 25:     80-90% nodes gần
```

---

## 7. CÁCH CHẠY NHANH

### Chạy Baseline
```bash
# Mở Cooja → Load wsn-2sink-full.csc → Start
# Đợi ~10 phút → Stop
# Log: data/logs/run.log
python analyze.py data/logs/run.log
```

### Chạy Attack
```bash
# Sửa node.c: #define ATTACK_BLACKHOLE 1
cd contiki-ng
make clean && make TARGET=cooja
# Mở Cooja → Load → Start
python analyze.py data/logs/run_attack.log
```

### So sánh
```bash
python compare_scenarios.py data/logs/run.log data/logs/run_attack.log
# Output: 5 charts so sánh
```

---

## 8. XỬ LÝ LỖI THƯỜNG GẶP

| Lỗi | Triệu chứng trong log | Nguyên nhân | Sửa |
|-----|----------------------|-------------|-----|
| **Nodes chết sớm** | `DEAD time_alive_s=157` (quá nhỏ) | Đặt xa sink | Chạy `validate_placement.py` |
| **DEAD trùng** | Cùng node nhiều DEAD events | Bug process không exit | Dùng `node_is_dead` flag |
| **PDR thấp** | RX << TX | Blackhole/routing lỗi | Kiểm tra TXFAIL, parent switches |
| **Energy âm** | `energy_mj=-100` | Overflow | Dùng double comparison |

---

## 9. CẤU TRÚC FILE

```
src/
├── nodes/node.c              # Code sensor (có ATTACK flags)
├── data/logs/run.log         # Log mô phỏng
├── data/results/
│   ├── full_analysis.csv     # 15 chỉ số
│   ├── summary_4metrics.csv  # 4 chỉ số chính
│   └── charts/               # 3 PNG charts
├── analyze.py                # Parse log → CSV + Charts
├── compare_scenarios.py      # So sánh 2 logs
├── wsn-2sink-full.csc       # File simulation Cooja
└── PROJECT_OVERVIEW.md       # File này
```

---

## PHỤ LỤC: REGEX PARSE LOG

```python
PATTERNS = {
  'gen':    r'(?P<t>[\d:.]+)\s+ID:(?P<id>\d+).*GEN cluster=(?P<cl>\d+) node=(?P<node>\d+) gen_count=(?P<gc>\d+)',
  'tx':     r'(?P<t>[\d:.]+)\s+ID:(?P<id>\d+).*TX cluster=(?P<cl>\d+) node=(?P<node>\d+) seq=(?P<seq>\d+) energy_mj=(?P<e>\d+) bytes=(?P<b>\d+)',
  'rx':     r'(?P<t>[\d:.]+)\s+ID:(?P<id>\d+).*RX sink=(?P<sink>\d+) cluster=(?P<cl>\d+) node=(?P<node>\d+) seq=(?P<seq>\d+) energy_mj=(?P<e>\d+) bytes=(?P<b>\d+) latency_ms=(?P<lat>\d+)',
  'dead':   r'(?P<t>[\d:.]+)\s+ID:(?P<id>\d+).*DEAD cluster=(?P<cl>\d+) node=(?P<node>\d+) time_alive_s=(?P<alive>\d+) last_seq=(?P<seq>\d+) total_gen=(?P<gen>\d+) total_sent=(?P<sent>\d+)',
  'status': r'(?P<t>[\d:.]+)\s+ID:(?P<id>\d+).*STATUS node=(?P<node>\d+) energy_mj=(?P<e>\d+) duty_pct=(?P<duty>-?\d+) rank=(?P<rank>\d+)',
  'txfail': r'(?P<t>[\d:.]+)\s+ID:(?P<id>\d+).*TXFAIL cluster=(?P<cl>\d+) node=(?P<node>\d+) gen_count=(?P<gc>\d+)',
}
```

---

**Phiên bản**: 1.0 - Tinh giản  
**Cập nhật**: 2026-08-20
