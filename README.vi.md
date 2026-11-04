# Data to App

### File của bạn trở thành phần mềm. Quyết định của bạn được giữ qua lần nhập tiếp theo.

[English](README.md) · [Tiếng Việt](README.vi.md) · [한국어](README.ko.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Português](README.pt-BR.md) · [简体中文](README.zh-CN.md) · [ไทย](README.th.md) · [Français](README.fr.md)

**Giao cho Claude hoặc Codex những file và một công việc thật. Nhận lại ứng dụng có thể chạy, kiểm tra và làm chủ.**

Data to App biến CSV và Excel thành công cụ vận hành hiểu rõ nguồn dữ liệu: tìm kiếm bản ghi, view hữu ích, chỉnh sửa được phép và nhập lại theo từng đợt. Agent định hình workflow; bộ máy Python/SQLite có hành vi xác định tách riêng bản ghi nguồn, chỉnh sửa local và snapshot mới. Bạn nhận app chạy được, source và dữ liệu local.

**[Dựng workspace đầu tiên](#chạy-workspace-tồn-kho)** · **[Cài cho Claude hoặc Codex](docs/INSTALL.md)** · **[Khám phá hợp đồng dữ liệu](docs/DATA-CONTRACT.md)** · **[Khám phá demo có hướng dẫn](https://hieunguyenak92.github.io/data-to-app/)**

![Ứng dụng tồn kho tổng hợp được tạo bằng Data to App](docs/assets/workspace.jpg)

*Ảnh chụp runtime local thật với dữ liệu giả. Snapshot mới đã được đối soát và quyết định chỉnh sửa được giữ lại.*

> **Mỗi lần cập nhật đều rõ ràng.** Giá trị nguồn là `12`. Bạn sửa thành `20`. File mới ghi `14`. Data to App giữ `20` của bạn và hiển thị xung đột nguồn/local/dữ liệu mới để bạn quyết định. Thay đổi đồng thuận tự hội tụ; khác biệt cần phán đoán luôn được thể hiện.

## Bắt đầu bằng công việc thực tế

Sau khi [cài skill](docs/INSTALL.md), giao việc cho agent:

> Dùng Data to App với `./exports`. Dựng công cụ tồn kho local có tìm kiếm, danh sách hàng dưới ngưỡng, chỉnh sửa ngưỡng nhập hàng và ghi chú. Giữ những chỉnh sửa đó khi tôi nhập file kế tiếp và hiển thị các thay đổi cần quyết định. Khởi chạy app và kiểm tra các thao tác chính.

Skill dẫn agent qua việc kiểm tra file, chọn identity và thao tác, xây app rồi sử dụng thử. Bạn mô tả công việc; agent xử lý mô hình kỹ thuật. Nếu khóa, đơn vị hoặc quy tắc nghiệp vụ còn mơ hồ và ảnh hưởng kết quả, agent có thể cần một câu trả lời rõ từ bạn.

Các trường hợp phù hợp: file tồn kho/đơn hàng, danh sách liên hệ cần chỉnh sửa liên tục, hoặc bản ghi dự án/dịch vụ được cập nhật qua file định kỳ. Bản đầu tập trung vào các bảng local có khóa riêng và workflow được yêu cầu.

## Được thiết kế cho lần nhập tiếp theo

| Năng lực | Giá trị cụ thể |
| --- | --- |
| **Phân tích identity** | Đưa bằng chứng về khóa ứng viên, ô thiếu, dữ liệu trùng và mã có số 0 đầu. |
| **Kiểm tra phép ghép trước** | Phát hiện khóa không khớp và nguy cơ nhân số dòng trước khi agent kết hợp dữ liệu. |
| **Đối chiếu ba phía** | Tách nguồn, local và dữ liệu mới; quyết định theo từng trường khi chỉnh sửa xung đột. |
| **Preview nhập dữ liệu** | Xem bản ghi mới, cập nhật, thiếu và xung đột trước khi áp dụng snapshot. |
| **Giao diện vận hành** | Tìm kiếm, view được cấu hình, chỉnh sửa được phép, giải quyết xung đột, lịch sử và export CSV. |
| **Source có thể mang đi** | App Python/SQLite cùng assets local, chạy độc lập với skill đã cài. |

Những cơ chế này cung cấp bằng chứng cho agent ra quyết định. Một cột duy nhất trong file là khóa ứng viên, chưa chứng minh đó là identity nghiệp vụ. Phép ghép chạy thành công cũng chưa chứng minh tổng số có đúng ý nghĩa bạn cần.

## Chạy workspace tồn kho

Cần **Python 3.10+**. Đường CSV và runtime được tạo dùng thư viện chuẩn. Dữ liệu mẫu hoàn toàn tổng hợp.

```bash
git clone https://github.com/hieunguyenak92/data-to-app.git
cd data-to-app
python3 skills/data-to-app/scripts/dta.py demo --out ./inventory-app
python3 inventory-app/app.py --port 8765
```

Mở **http://127.0.0.1:8765**. Tìm một sản phẩm, mở phần chỉnh sửa, đổi trường được phép rồi export. Trạng thái nằm trong database SQLite riêng của workspace và được giữ khi khởi động lại app.

Để xem trước snapshot sản phẩm tiếp theo, mở terminal khác tại thư mục repo:

```bash
python3 skills/data-to-app/scripts/dta.py import ./inventory-app --table products --file skills/data-to-app/assets/examples/inventory/next/products.csv
```

Thêm `--apply` để áp dụng, hoặc dùng preview và xác nhận trong app. Thử sửa một trường cũng thay đổi trong file mới để thấy luồng giải quyết xung đột.

Mỗi lần import là **snapshot đầy đủ của một bảng**. Bản ghi vắng mặt được đánh dấu thiếu và vẫn giữ lại. Vì vậy, file export chỉ chứa một phần sẽ khiến các bản ghi bị bỏ qua được đánh dấu thiếu. Thay đổi schema và khóa trùng có giá trị xung đột bị từ chối trước khi ghi dữ liệu.

## Dùng file của bạn

CSV là bảng dạng văn bản; XLSX là workbook Excel. Với XLSX, cài bộ đọc tùy chọn trong môi trường Python chạy toolkit:

```bash
python3 -m pip install openpyxl==3.1.5 defusedxml==0.7.1 et-xmlfile==2.0.0
```

Giới hạn đầu vào: **10 MiB mỗi file, 50,000 dòng mỗi bảng, 200 cột và 1,000,000 ô**. XLSX mặc định dùng worksheet đầu tiên và cảnh báo khi có sheet khác. Công thức không được tính lại.

Bắt đầu bằng prompt ở trên hoặc kiểm tra file trực tiếp:

```bash
python3 skills/data-to-app/scripts/dta.py inspect ./exports
```

Agent dùng profile để cấu hình mô hình và dựng workspace. [Hướng dẫn cài và CLI bằng tiếng Anh](docs/INSTALL.md) trình bày đường kỹ thuật.

## Export, quyền sở hữu và giới hạn

Export CSV chứa giá trị đang có hiệu lực của các bản ghi active, gồm chỉnh sửa local đã chấp nhận. Cơ chế chống công thức spreadsheet có thể thêm dấu nháy đơn vào ô export có rủi ro; giá trị lưu bên trong không đổi. Bản ghi thiếu vẫn được giữ local.

Runtime được tạo bind vào `127.0.0.1`, phục vụ assets local và không cần hosted service cho các thao tác cốt lõi. Trong lúc agent xây app, chính sách truy cập file và xử lý dữ liệu của AI host vẫn áp dụng. Database, input và export có thể chứa thông tin nhạy cảm. [Chi tiết quyền riêng tư bằng tiếng Anh](docs/PRIVACY.md).

Bản này là workspace local, chưa có xác thực nhiều người dùng hoặc bảo đảm triển khai cloud. Nó không thực thi công thức Excel, tự hiểu mọi quy tắc nghiệp vụ, hỗ trợ migration schema tùy ý hoặc hứa phục hồi mọi dữ liệu. Kiểm tra kết quả quan trọng trước khi dùng vận hành.

**Bắt đầu với dữ liệu mẫu. Sau đó giao cho agent một công việc thật.**
