# Fix Git Submodule Issues

## Vấn đề:
1. **Git submodule corrupt**: `fatal: bad object HEAD` trong `src/contiki-ng`
2. **Windows path too long**: Nhiều file paths > 260 characters

## Giải pháp: CHỈ COMMIT CODE CỦA BẠN, BỎ QUA SUBMODULE

### Bước 1: Add files bạn thực sự cần commit

**KHÔNG** dùng `git add .` (sẽ thêm cả submodule broken)

Thay vào đó, add từng folder/file:

```cmd
git add src\nodes\
git add src\monitoring\
git add src\data\
git add src\wsn-2sink-full.csc
git add .gitignore
```

### Bước 2: Commit changes

```cmd
git commit -m "feat: version update with RPL global repair + monitoring dashboard

- Version update mỗi 30 phút
- RPL global repair trigger rerouting
- Dashboard hiển thị DEAD nodes
- Active nodes count đúng
- Parse SINK_START và VERSION_UPDATE messages"
```

### Bước 3: Push (nếu cần)

```cmd
git push
```

## Nếu vẫn bị lỗi submodule:

### Option A: Xóa submodule khỏi git tracking (KHUYẾN NGHỊ)

```cmd
git rm --cached src\contiki-ng
git commit -m "Remove broken contiki-ng submodule"
```

Sau đó add `.gitignore`:
```
src/contiki-ng/
```

### Option B: Fix submodule (phức tạp hơn)

```cmd
cd src\contiki-ng
git fsck --full
git gc --aggressive
```

Nếu không fix được:
```cmd
cd ..\..
rd /s /q src\contiki-ng
git submodule update --init --recursive
```

## Workaround nếu không cần version control cho contiki-ng:

### Chỉ commit code của bạn:

Create `.gitignore` ở root:
```
src/contiki-ng/
*.log
*.cooja
__pycache__/
*.pyc
venv/
.vscode/
```

Sau đó:
```cmd
git add .gitignore
git add src\nodes\sink.c
git add src\nodes\node.c
git add src\monitoring\
git add src\wsn-2sink-full.csc
git commit -m "Update: version update và monitoring"
git push
```

## Enable long paths on Windows (fix "Filename too long"):

**Run as Administrator:**
```cmd
git config --system core.longpaths true
```

Hoặc chỉ cho repo này:
```cmd
git config core.longpaths true
```

## TL;DR - QUICK FIX:

```cmd
# 1. Bỏ qua submodule
git rm --cached src\contiki-ng

# 2. Add các files bạn sửa
git add src\nodes\sink.c src\monitoring\ src\wsn-2sink-full.csc

# 3. Commit
git commit -m "feat: version update + monitoring dashboard"

# 4. Push
git push
```

Contiki-NG là external dependency, không cần commit vào repo của bạn!
