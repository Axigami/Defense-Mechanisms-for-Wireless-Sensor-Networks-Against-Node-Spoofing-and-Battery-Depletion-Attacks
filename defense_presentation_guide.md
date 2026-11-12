# HƯỚNG DẪN THUYẾT TRÌNH & BÁO CÁO DEMO HỆ THỐNG PHÒNG THỦ WSN
**Đề tài:** Cơ chế phòng vệ mạng cảm biến không dây chống tấn công Giả mạo Nút mạng (Node Spoofing / Sybil) và Tiêm dữ liệu sai lệch (False Data Injection)

---

## 1. TỔNG QUAN HỆ THỐNG PHÒNG THỦ (EXECUTIVE SUMMARY)
Hệ thống phòng thủ được thiết kế theo mô hình **Đường ống 4 Lớp tuần tự (4-Layer Sequential Pipeline)** kết hợp với **Bộ Quản Lý Điểm Tin Cậy (TrustManager - Mô hình phân phối Beta)**, bảo vệ mạng WSN toàn diện từ tầng vật lý, tầng mạng đến tầng dữ liệu ứng dụng:

```
[ Gói tin đến ] 
       │
       ▼
┌────────────────────────────────────────────────────────────────────────┐
│ LỚP 1: Bóc tách cú pháp & Tiền xử lý dữ liệu (Parser & Sanitizer)      │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ LỚP 2: Đối chiếu Không gian Tọa độ & Phát hiện ID Giả (Ghost ID)       │
│  → Chặn tức thì các định danh không tồn tại trên sơ đồ mạng vật lý     │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ LỚP 3: Dấu vân tay Sóng Vô Tuyến (Physical RSSI Fingerprinting)        │
│  → Phát hiện sai lệch vị trí vật lý (MISMATCH) & Khóa vùng sóng (ZONE) │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ LỚP 4: Giao thức Xác minh Cháy Không Gian - Thời Gian (Spatio-Temporal)│
│  → Phân biệt Cháy thật và Báo cháy giả (FDI) qua đồng thuận lân cận    │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ BỘ QUẢN LÝ ĐIỂM TIN CẬY (TrustManager - Mô hình Beta Distribution)     │
│  → Quyết định Đánh giá: Chấp nhận gói tin, Phạt điểm, hoặc BLACKLIST   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. MA TRẬN ĐÁNH CHẶN 3 KỊCH BẢN TẤN CÔNG

| Kịch Bản Tấn Công | Hành Vi & Mục Đích Của Kẻ Tấn Công | Lớp Phòng Thủ Đánh Chặn | Nguyên Lý Phát Hiện & Cơ Chế Xử Lý | Hiển Thị Trên Video Demo / Dashboard |
| :--- | :--- | :--- | :--- | :--- |
| **1. Sybil Attack** *(Giả mạo đa định danh)* | Node 53 phát sinh hàng loạt **định danh ảo (ID 100–110)** kèm địa chỉ IPv6 nguồn giả mạo, gửi dữ liệu nhiệt độ 85°C liên tục về Sink nhằm gây nghẽn mạng và làm sai lệch thống kê. | **Lớp 2 (Ghost ID)**<br>+ **Lớp 3 (RSSI Profiling)** | • **Lớp 2:** Đối chiếu `TopologyMap` phát hiện ID nằm ngoài danh sách nút vật lý $\rightarrow$ **Chặn tức thì (Instant Block)**.<br>• **Lớp 3:** Nhận diện nhiều ID phát ra từ cùng một mức công suất thu RSSI của Node 53 $\rightarrow$ **Khóa vùng phát sóng (Zone Block)**. | • Cảnh báo đỏ trên Feed: `GHOST ID DETECTED: NODE 10x`.<br>• Nút giả mạo chuyển sang trạng thái `BLOCKED`, điểm tin cậy giảm xuống `0.98%`, bị cô lập vĩnh viễn. |
| **2. Hijacked Node** *(Chiếm quyền nút hợp lệ & Bơm dữ liệu giả FDI)* | Kẻ tấn công chiếm quyền điều khiển các nút hợp lệ (có ID thật, tọa độ thật, RSSI hợp lệ) và đồng loạt gửi báo cáo nhiệt độ cao (85°C) để gây báo động giả và làm cạn kiệt tài nguyên mạng. | **Lớp 4: Fire Confirmation Protocol** *(Không gian - Thời gian)* | • **Kiểm tra tức thời:** Phát hiện bất thường nhảy cóc không gian $> 35\text{m}$ trong $< 5\text{s}$ (`Teleporting Fire`) hoặc bùng phát đồng loạt (`Sync Burst`).<br>• **Cửa sổ quan sát 10s (`Observing`):** Tạm hoãn phán quyết và đóng băng điểm tin cậy để chờ dữ liệu láng giềng.<br>• **Phán quyết sau 10s:** Nút báo cháy đơn độc hoặc thông đồng bảo lãnh chéo $\rightarrow$ **HIJACK DETECTED** $\rightarrow$ Cô lập vào Blacklist. | • Trạng thái ban đầu: `OBSERVING` (đóng băng điểm tin cậy).<br>• Khi phát hiện vi phạm: Hiện cảnh báo đỏ `HIJACK DETECTED` / `LONE NODE ANOMALY` / `COLLUSION DETECTED`, nút chuyển sang `BLOCKED`. |
| **3. Distraction Attack** *(Tấn công nghi binh kết hợp Cháy thật)* | Đám cháy thực tế bùng phát tại cụm Node 30, 31, 32. Đồng thời, Node 54 phát động tấn công nghi binh (phát ID 200+ với nhiệt độ 25°C) nhằm gây nhiễu hệ thống phòng thủ. | **Lớp 2 + Lớp 3** (chặn nghi binh)<br>kết hợp **Lớp 4** (xác nhận cháy thật) | • **Nút nghi binh (Node 54):** Bị Lớp 2 & Lớp 3 cô lập với lỗi `SYBIL_CLONE` / `ZONE_BLOCK`, không làm kích hoạt nhầm trạng thái làn sóng tấn công Hijack.<br>• **Cụm cháy thật (Node 30, 31, 32):** Lớp 4 xác nhận sự gia tăng nhiệt độ đồng thuận trong bán kính $15\text{m}$ $\rightarrow$ **TRUE FIRE CONFIRMED**. | • Các ID nghi binh bị cô lập với nhãn `BLOCKED`.<br>• Cụm nút cháy thật duy trì trạng thái `Alive`, giữ `100%` điểm tin cậy và kích hoạt biểu ngữ khẩn cấp: `CRITICAL TEMPERATURE ALERT`. |

---

## 3. CHI TIẾT CƠ CHẾ HOẠT ĐỘNG CỦA TỪNG LỚP PHÒNG VỆ

### 🛡️ LỚP 1: Bóc Tách Cú Pháp & Tiền Xử Lý Dữ Liệu (Data Parser & Filter)
* **Nhiệm vụ:** Trích xuất thông tin định lượng từ luồng dữ liệu nhật ký Cooja/Sink (`Node ID`, `RSSI`, `Nhiệt độ`, `SeqNo`, `Thời gian mô phỏng`).
* **Đặc điểm:** Tách biệt lưu lượng điều khiển định tuyến RPL (DIO/DAO/DIS) khỏi lưu lượng dữ liệu cảm biến ứng dụng để đảm bảo độ chính xác của các bộ lọc thống kê.

### 🛡️ LỚP 2: Đối Chiếu Không Gian Tọa Độ & Phát Hiện Định Danh Giả (Ghost ID Detection)
* **Nhiệm vụ:** Ngăn chặn kẻ tấn công tự phát sinh các định danh ảo (Sybil IDs).
* **Cơ chế hoạt động:**
  * Hệ thống tự động trích xuất bản đồ tọa độ mạng thực tế từ file cấu hình mô phỏng Cooja (`.csc`). Mạng tiêu chuẩn gồm **2 trạm Sink** (`Sink 1` và `Sink 27`), **50 nút cảm biến hợp lệ** chia làm 2 cụm (ID tối đa đến `52`), cùng nút đóng vai trò kẻ tấn công (`Node 53` hoặc `Node 54`).
  * Khi nhận gói tin, nếu `node_id` vượt quá dải định danh hợp lệ hoặc không tồn tại trên bản đồ tọa độ vật lý:
    $$\text{ID} \notin \text{TopologyMap} \implies \text{GHOST ID DETECTED}$$
  * **Hành động xử lý:** Áp dụng mức phạt nghiêm trọng ($\beta + 100$) $\rightarrow$ **Chặn tức thì (Instant Block)**, đưa định danh giả vào danh sách đen (`Blacklist`) vĩnh viễn và dừng xử lý gói tin ngay tại Lớp 2, không chuyển tiếp xuống Lớp 4 để bảo vệ tính toàn vẹn của dữ liệu nhiệt độ.

### 🛡️ LỚP 3: Dấu Vân Tay Sóng Vô Tuyến (Physical RSSI Fingerprinting)
* **Nhiệm vụ:** Phát hiện kẻ tấn công cố định tại một vị trí vật lý nhưng giả mạo định danh của các nút mạng khác.
* **Cơ chế hoạt động:**
  1. **Giai đoạn Học tĩnh (250 gói tin đầu tiên):** Hệ thống thu thập cường độ tín hiệu thu RSSI của từng nút trong điều kiện không có tấn công để xây dựng cơ sở dữ liệu `Baseline RSSI`.
  2. **Giai đoạn Giám sát chủ động:** Đối chiếu từng gói tin mới với hồ sơ đã học:
     $$\Delta \text{RSSI} = |\text{RSSI}_{\text{actual}} - \text{Baseline RSSI}|$$
     * Nếu $\Delta \text{RSSI} > 3.0\text{ dBm}$: Xác định tín hiệu phát ra từ vị trí vật lý không khớp với hồ sơ đăng ký $\rightarrow$ Cảnh báo `RSSI MISMATCH`.
  3. **Cơ chế Khóa vùng phát sóng (`Zone Blacklisting`):** Nếu một mức RSSI liên tục xuất hiện trong các gói tin vi phạm định danh, hệ thống tự động phong tỏa toàn bộ dải băng tần RSSI tương ứng ($\pm 2.0\text{ dBm}$). Mọi gói tin phát ra từ vùng không gian này đều bị đánh chặn (`ZONE_BLOCK`).

### 🛡️ LỚP 4: Giao Thức Xác Minh Cháy Không Gian - Thời Gian (Spatio-Temporal Fire Protocol)
* **Nhiệm vụ:** Chống lại tấn công tiêm dữ liệu sai lệch (False Data Injection - FDI), phân biệt chính xác giữa sự kiện cháy rừng thực tế và báo động giả.
* **Quy trình xác minh 3 giai đoạn:**
  1. **Dải gia nhiệt tiền đám cháy ($29^\circ\text{C} - 60^\circ\text{C}$):** Cho phép dữ liệu nhiệt độ tăng dần tự nhiên đi qua hệ thống để cập nhật bảng `latest_temps` và hiển thị lên giao diện giám sát mà không làm sai lệch ngưỡng nền môi trường ($3\sigma$).
  2. **Kiểm tra bất thường vật lý tức thời (Immediate Anomaly Check cho $\text{Temp} > 60^\circ\text{C}$):**
     * *Bất thường không gian (`Teleporting Fire`):* Hai nút cách nhau $> 35\text{m}$ (khác cụm) cùng báo nhiệt độ $> 60^\circ\text{C}$ với độ lệch thời gian $< 5\text{s}$ $\rightarrow$ Vi phạm quy luật lan truyền nhiệt $\rightarrow$ **HIJACK DETECTED**.
     * *Bất thường đồng bộ (`Sync Burst`):* $\ge 5$ nút trong bán kính $15\text{m}$ đồng loạt tăng vọt lên $> 60^\circ\text{C}$ trong $< 5\text{s}$ $\rightarrow$ Báo động giả đồng loạt $\rightarrow$ **HIJACK DETECTED**.
     * *Đứt gãy gradient nhiệt (`Temp Cliff`):* Tâm cụm có $\ge 5$ nút báo nóng nhưng vành đai $15\text{m} - 25\text{m}$ có $\ge 2$ nút giữ nhiệt độ $< 40^\circ\text{C}$ $\rightarrow$ **HIJACK DETECTED**.
  3. **Cửa sổ quan sát 10 giây & Phán quyết tương quan cụm:**
     * Khi một nút báo nhiệt độ $> 60^\circ\text{C}$ và chưa vi phạm các bẫy tức thời, hệ thống chuyển nút sang trạng thái **OBSERVING trong 10.0 giây** (tương đương 3–4 chu kỳ truyền tin qua lịch TSCH và cây định tuyến RPL). Trong thời gian này, điểm tin cậy của nút được đóng băng.
     * **Phán quyết khi kết thúc 10 giây:**
       * Nếu có $\ge 1$ nút láng giềng hợp lệ trong bán kính $15\text{m}$ cùng báo nhiệt độ $\ge 55^\circ\text{C}$ $\rightarrow$ Xác nhận **TRUE FIRE CONFIRMED** (duy trì 100% điểm tin cậy).
       * Nếu nút báo cháy đơn độc, không có nút láng giềng nào trong bán kính $15\text{m}$ xác nhận $\rightarrow$ **Lone Node Anomaly** $\rightarrow$ **HIJACK DETECTED** $\rightarrow$ Cô lập vào danh sách đen.
     * **Chống thông đồng bảo lãnh chéo (`Collusion Detection`):** Khi phát hiện làn sóng tấn công (`>= 3` nút bị chặn do Hijack trong 120s), hệ thống yêu cầu phải có ít nhất một nút láng giềng độc lập (chưa từng bị cảnh báo) làm nhân chứng. Nếu tất cả các nút láng giềng báo nóng đều đang thuộc diện nghi vấn $\rightarrow$ Kết luận **COLLUSION DETECTED (Mutual Vouching)** và cô lập toàn bộ cụm thông đồng.

### 🛡️ BỘ QUẢN LÝ ĐIỂM TIN CẬY (TrustManager - Beta Distribution Model)
* Điểm tin cậy khởi tạo: **90.9%** ($\alpha = 10.0, \beta = 1.0$).
* **Quy tắc Đánh giá & Cô lập:**
  * Công thức tính điểm tin cậy:
    $$\text{Trust Score} = \frac{\alpha}{\alpha + \beta} \times 100\%$$
  * Khi $\text{Trust Score} < 40\% \rightarrow$ **ĐƯA VÀO DANH SÁCH ĐEN (BLACKLIST - Cách ly vĩnh viễn khỏi mạng)**.
  * Vi phạm nghiêm trọng (`HIJACK`, `SYBIL_CLONE`, `ZONE_BLOCK`): Thiết lập $\alpha = 1.0$, cộng phạt $\beta + 100.0$ $\rightarrow$ Điểm tin cậy giảm xuống **0.98%**, nút bị cô lập ngay lập tức.
  * Sai lệch tín hiệu nhẹ (`RSSI MISMATCH`): Cộng phạt $\beta + 4.0$ (trừ điểm lũy tiến nhằm tránh phạt nhầm do nhiễu đường truyền).

---

## 4. KỊCH BẢN THUYẾT TRÌNH TỪNG BƯỚC KHI TRÌNH CHIẾU VIDEO DEMO

### ⏱️ Phút 0:00 – 0:45: Giới thiệu kiến trúc mạng & Giai đoạn Học (Learning Phase)
> *"Kính thưa thầy cô và hội đồng, đây là giao diện giám sát thời gian thực của mạng WSN gồm 2 cụm với 2 trạm Sink (Sink 1 và Sink 27) cùng 50 nút cảm biến hợp lệ. Trong 250 gói tin đầu tiên, hệ thống hoạt động ở chế độ **LEARNING**, thu thập dữ liệu cường độ tín hiệu thu RSSI để xây dựng hồ sơ `Baseline RSSI` cho từng nút và nạp bản đồ tọa độ vật lý. Khi hoàn tất, hệ thống chuyển sang trạng thái **ARMED** — toàn bộ 4 lớp phòng thủ chính thức đi vào giám sát thời gian thực."*

### ⏱️ Phút 0:45 – 1:45: Demo Kịch bản 1 — Ngăn chặn tấn công Sybil (Ghost ID & Zone Block)
> *"Tại kịch bản thứ nhất, trên bảng điều khiển Attacker, khi kích hoạt **Deploy Sybil Attack**, nút tấn công Node 53 bắt đầu phát tán các gói tin mang định danh giả từ 100 đến 110 kèm nhiệt độ giả 85°C. Ngay khi gói tin đầu tiên đến Sink, **Lớp 2 (Coordinate Map)** phát hiện định danh này không tồn tại trên sơ đồ mạng hợp lệ. Hệ thống lập tức đưa ra phán quyết **GHOST ID DETECTED**, hạ điểm tin cậy xuống 0.98% và đưa vào danh sách đen (`BLOCKED`). Đồng thời, sau 3 lần phát hiện vi phạm từ cùng một mức công suất thu, **Lớp 3** tự động kích hoạt **ZONE BLOCK**, phong tỏa toàn bộ dải sóng RSSI của Node 53."*

### ⏱️ Phút 1:45 – 2:50: Demo Kịch bản 2 — Phát hiện Hijacked Node (Tấn công FDI phối hợp)
> *"Tiếp theo là kịch bản chiếm quyền điều khiển các nút hợp lệ (Node 2 đến Node 16). Do các nút này sử dụng định danh thật và phát sóng từ vị trí vật lý thật, chúng vượt qua Lớp 2 và Lớp 3. Khi kẻ tấn công bơm dữ liệu nhiệt độ tăng vọt lên trên 60°C–85°C, **Lớp 4 (Spatio-Temporal Fire Protocol)** lập tức được kích hoạt. Các nút vi phạm quy luật không gian - thời gian (`Teleporting Fire`) bị chặn tức thì; các nút còn lại được đưa vào trạng thái **OBSERVING** trong 10 giây và đóng băng điểm tin cậy. Sau 10 giây, hệ thống đối chiếu bán kính 15m và kích hoạt cơ chế phát hiện đơn độc (**Lone Node Anomaly**) hoặc phát hiện bảo lãnh chéo (**Collusion Detection**), cô lập hoàn toàn các nút bị chiếm quyền vào trạng thái **BLOCKED**."*

### ⏱️ Phút 2:50 – 4:00: Demo Kịch bản 3 — Chống tấn công Nghi binh & Bảo toàn Cảnh báo Cháy thật (Distraction Attack)
> *"Cuối cùng là kịch bản kết hợp: Một đám cháy thực tế bùng phát tại cụm Node 30, 31, 32 trong khi Node 54 phát động tấn công nghi binh bằng các định danh giả (ID 200+) báo nhiệt độ bình thường 25°C. Trên giao diện giám sát, **Lớp 2 và Lớp 3 nhanh chóng nhận diện và cô lập toàn bộ các định danh nghi binh từ Node 54 (`BLOCKED`)**, trong khi **Lớp 4 ghi nhận sự gia tăng nhiệt độ tự nhiên và đồng thuận không gian giữa ba nút 30, 31, 32 trong bán kính 15m**. Kết quả là hệ thống xác nhận chính xác **TRUE FIRE CONFIRMED**, duy trì 100% điểm tin cậy cho cụm nút cháy thật và kích hoạt biểu ngữ cảnh báo cháy khẩn cấp trên Dashboard."*

---

## 5. CÂU HỎI PHẢN BIỆN THƯỜNG GẶP (Q&A)

**Câu hỏi 1: Tại sao hệ thống không sử dụng chữ ký số hoặc mật mã khóa công khai (PKI) để chống giả mạo Sybil mà sử dụng phân tích RSSI kết hợp bản đồ tọa độ?**
* **Trả lời:** Các nút mạng cảm biến không dây hoạt động trên vi điều khiển tài nguyên hạn chế (bộ nhớ RAM/ROM nhỏ, năng lượng pin giới hạn ở mức 15.000 mJ). Các thuật toán mật mã bất đối xứng tiêu tốn nhiều chu kỳ CPU và năng lượng truyền tải bản tin xác thực. Phương pháp đối chiếu **Bản đồ tọa độ không gian kết hợp Dấu vân tay sóng vô tuyến RSSI** chuyển toàn bộ gánh nặng tính toán về trạm Sink (nơi có nguồn điện và năng lực xử lý mạnh), giúp các nút cảm biến tiết kiệm tối đa năng lượng pin.

**Câu hỏi 2: Cửa sổ quan sát 10 giây tại Lớp 4 có làm chậm trễ việc phát cảnh báo cháy trong thực tế không?**
* **Trả lời:** Không ảnh hưởng đến tính thời gian thực của hệ thống cảnh báo cháy. Trong thực tế, một đám cháy vật lý phát triển theo thang thời gian tính bằng phút. Trong mạng WSN sử dụng giao thức MAC **TSCH (IEEE 802.15.4e)** và định tuyến đa bước nhảy **RPL**, chu kỳ phát tin khi có biến động nhiệt độ là 3 giây/gói. Cửa sổ 10 giây (tương đương khoảng 3 chu kỳ truyền tin) là khoảng thời gian tối ưu để thu thập đủ các gói tin từ các nút láng giềng vượt qua độ trễ hàng đợi đa bước nhảy, giúp loại bỏ báo động giả mà vẫn đảm bảo cảnh báo sớm.

**Câu hỏi 3: Nếu kẻ tấn công chiếm quyền nhiều nút nằm sát nhau (trong bán kính 15m) để chúng tự xác nhận chéo cho nhau thì Lớp 4 xử lý như thế nào?**
* **Trả lời:** Hệ thống đã tích hợp cơ chế **Nhận diện làn sóng tấn công và Chống thông đồng (`Attack Wave Awareness & Collusion Detection`)**. Khi hệ thống ghi nhận từ 3 nút trở lên bị khóa do hành vi Hijack trong vòng 120 giây, điều kiện xác nhận cháy thật sẽ được siết chặt: bắt buộc phải có ít nhất một nút láng giềng đóng vai trò nhân chứng độc lập (chưa từng nằm trong diện cảnh báo nghi vấn). Nếu tất cả các nút láng giềng báo nóng đều là các nút đang bị theo dõi nghi vấn, hệ thống sẽ kết luận đây là hành vi thông đồng bảo lãnh chéo (**Mutual Vouching**) và cô lập toàn bộ cụm nút đó.
