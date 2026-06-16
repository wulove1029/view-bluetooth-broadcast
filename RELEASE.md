# 發布流程說明（Release Guide）

本專案採用 **GitHub Actions 全自動發布**。設定檔：[.github/workflows/auto-release.yml](.github/workflows/auto-release.yml)

> 一句話總結：**改完程式 → commit → push 到 master**，版本號遞增、打包 exe、建立 GitHub Release 全部自動完成。

---

## 一、正常發布流程（你只要做這 3 步）

```bash
git add view_bluetooth_broadcast.py
git commit -m "fix: 你的修改說明"     # ⚠️ 訊息裡千萬不要有 [skip ci]
git push origin master
```

push 之後，到 GitHub 的 **Actions** 分頁就能看到 workflow 正在跑；跑完後 **Releases** 分頁會出現新版本與可下載的 `BLE-Scanner.zip`。

---

## 二、自動化做了什麼（三個階段）

| 階段 | 執行平台 | 動作 |
|------|----------|------|
| 1. `bump-version` | Linux | 讀 `VERSION` → patch 自動 **+1** → 寫回 `VERSION` → commit（帶 `[skip ci]`）→ 建立 tag `vX.Y.Z` → push |
| 2. `build-exe` | Windows | `pyinstaller --onedir --windowed` 打包 → 壓成 `BLE-Scanner.zip` → 上傳 artifact |
| 3. `create-release` | Linux | 下載 artifact → 建立 GitHub Release 並附上 `BLE-Scanner.zip` |

打包指令（CI 內實際執行，無需本機操作）：

```bash
pyinstaller --onedir --windowed --name "BLE-Scanner" --add-data "VERSION;." --collect-data certifi view_bluetooth_broadcast.py
```

---

## 三、重要規則

- **版本號不用手動改**：workflow 會自動把 patch +1（例如 `1.0.21` → `1.0.22`）。
- **觸發條件**：push 到 `master` 且有改到 `view_bluetooth_broadcast.py` 或 `VERSION`。
- **跳過發布**：commit 訊息含 `[skip ci]` 會整個跳過，不會發布。
- **使用者怎麼用**：下載 `BLE-Scanner.zip` → 解壓 → 執行 `BLE-Scanner.exe`（需要藍芽 4.0+ 適配器，Windows 10/11 64-bit）。
- 採用 **onedir + zip** 打包，是為了解決防毒軟體誤刪暫存 DLL 的問題（單檔 onefile 會被誤刪）。
- 本機的 `BLE-Scanner.spec` 是給**本機手動測試打包**用的，正式發布走 CI 不會用到它。

---

## 四、常見問題與排錯

### 1. push 後沒有觸發發布
- 檢查 commit 訊息是不是含 `[skip ci]`。
- 檢查這次 commit 有沒有實際改到 `view_bluetooth_broadcast.py` 或 `VERSION`（只改其他檔案不會觸發）。

### 2. ⚠️ tag 已存在導致發布失敗（最容易踩的雷）
**原因**：本機 `VERSION` 的數字 **落後於** 已發布的最新 tag。
自動 bump 後產生的 tag 若已經存在，第一階段 `git push --tags` 會失敗，整個發布中斷。

**檢查方式**：

```bash
cat VERSION                          # 本機版本
git tag --sort=-v:refname | head -1  # 已發布的最新 tag
```

**規則**：`VERSION` 的值應該等於「最新 tag 的版本號」。
若 `VERSION` 比最新 tag 小，先把 `VERSION` 改成最新 tag 的版本（這樣下次 bump 才會產生全新且不重複的 tag），再 push。

### 3. 手動補發 / 重跑
GitHub → Actions → 選此 workflow → **Run workflow**（workflow 有設定 `workflow_dispatch`，可手動觸發）。

---

## 五、本機手動打包測試（選用，不影響正式發布）

想在本機驗證打包結果時：

```bash
pip install pyinstaller -r requirements.txt
pyinstaller BLE-Scanner.spec
# 產物在 dist/ 資料夾
```
