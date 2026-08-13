---
name: commit-message
description: Generate a git commit message following this project's convention (type prefix, imperative English summary under 10 words, optional body). Use whenever the user asks to write/draft a commit message or runs /commit-message.
---

# Commit Message 指令指南

撰寫 commit message 時，依照以下規則產生內容。

## 格式結構

```
<類型>: <簡短描述（動詞開頭，英文10字以內）>

<選填內文：說明為什麼這樣做，每行不超過 72 字>
```

## 類型對照表

| 類型 | 說明 |
|------|------|
| `feat` | 新增功能 |
| `fix` | 修復 bug |
| `docs` | 文件變更 |
| `style` | 格式調整（不影響邏輯） |
| `refactor` | 重構（非新功能也非修 bug） |
| `test` | 新增或修改測試 |
| `chore` | 建置流程或輔助工具變更 |
| `perf` | 效能改善 |
| `ci` | CI/CD 設定變更 |

## 注意事項

- 描述不加句號結尾
- 短描述使用祈使句（動詞開頭），例如 `fix: resolve login timeout` 而非 `fixed`/`fixes`
- 依實際 `git diff` / `git status` 內容判斷正確的類型，不要臆測
- 內文（body）為選填，只在需要說明「為什麼」時加入，而非重述程式碼做了什麼
