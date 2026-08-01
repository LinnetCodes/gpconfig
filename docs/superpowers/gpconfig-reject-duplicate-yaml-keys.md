# gpconfig 拒绝 YAML 重复键 Bugfix 需求

## 状态

- 状态：Draft
- 目标项目：`gpconfig`
- 基于版本：`0.3.4`
- 类型：Bugfix
- 优先级：在 Quant Types Portfolio v1 依赖此行为前完成

## 背景

`gpconfig` 目前在 `GPConfigManager._load_yaml_dict()` 中使用
`yaml.safe_load()` 读取 YAML。PyYAML 默认允许同一个 mapping 中出现重复键，并静默保留
最后一次出现的值。例如：

```yaml
portfolio:
  weight_mode: none
  weight_mode: explicit
```

加载结果中只剩下 `weight_mode: explicit`。后续 Pydantic 校验收到的已经是丢失了重复键信息的
普通 `dict`，因此无法判断用户是否写错了配置。

该行为也影响嵌套 mapping：

```yaml
portfolio:
  components:
    - symbol: 600000.XSHG
      symbol: 000001.XSHE
```

以及通过同一入口加载的 `global_env.yaml`。这会把含糊或错误的输入静默解释为有效配置，违反
Fail Early, Fail Fast 原则。

## 目标

1. `GPConfigManager._load_yaml_dict()` 加载的任何 YAML mapping，只要同一 mapping 中包含重复的
   显式键，就必须立即失败。
2. 检查必须覆盖任意嵌套深度，包括 list 中的 mapping。
3. 普通对象配置和 `global_env.yaml` 必须遵守相同规则。
4. 对外仍抛出 `gpconfig` 现有的 `ConfigValidationError`，并保留原始 YAML 异常作为
   `__cause__`。
5. 错误信息必须足以快速定位问题：至少包含配置文件路径、重复键，以及重复项的行号和列号；
   宜同时包含该键首次出现的位置。
6. 所有不含重复键的现有合法 YAML 行为保持不变。
7. 继续使用 PyYAML 的安全加载能力，不得为了实现检查而切换到不安全 Loader。

## 非目标

- 不在 YAML 加载层实现业务 schema 校验。
- 不检测不同 mapping 之间出现的同名键。
- 不检测重复值。
- 不增加 Portfolio 专用逻辑。
- 不自动合并、覆盖、改名或修复重复键。
- 不改变 `GPConfig` 的保存行为或对象构造协议。
- 不重试失败的加载。
- 本次 bugfix 不扩展或重新定义 YAML merge key（`<<`）语义；现有合法 merge 行为保持不变。
  本需求只禁止同一 mapping 节点中重复书写的显式键。

## 期望行为

### 顶层重复键

```yaml
portfolio:
  weight_mode: none
  weight_mode: explicit
```

加载失败，不得产生只保留最后一个值的 `dict`。

### 嵌套重复键

```yaml
portfolio:
  components:
    - symbol: 600000.XSHG
      symbol: 000001.XSHE
```

加载失败，错误信息应定位到第二个 `symbol`，并指出第一个 `symbol` 的位置。

### 不同 mapping 中的同名键

```yaml
portfolio_a:
  weight_mode: none
portfolio_b:
  weight_mode: none
```

加载成功；这不是重复键。

## 建议实现

在 `gpconfig` 的 YAML 加载层定义一个私有的 `yaml.SafeLoader` 子类，并为 mapping node 注册
重复键感知的 constructor：

1. 在 mapping 被转换为 Python `dict` 之前遍历其键节点。
2. 仅在同一个 mapping node 内维护已出现键及其 source mark。
3. 再次遇到相同显式键时，抛出 `yaml.constructor.ConstructorError`（或其他
   `yaml.YAMLError` 子类），携带首次出现和重复出现的 source mark。
4. 未发现重复键时，委托或等价执行 `SafeLoader` 的正常 mapping 构造逻辑。
5. `_load_yaml_dict()` 继续在现有 `except yaml.YAMLError` 边界把错误包装为
   `ConfigValidationError`，并使用异常链保留底层原因。

重复键检查应集中在 `_load_yaml_dict()` 的唯一 YAML 解析调用处。由于 `global_env.yaml` 已经通过
此方法加载，不应再为它实现第二套检查。

实现不得使用 `yaml.Loader`、`yaml.FullLoader` 或其他会扩大对象构造能力的 Loader。

## 错误契约

对于重复键，调用方观察到的异常应满足：

```text
ConfigValidationError
└── __cause__: yaml.YAMLError
```

错误文本的具体措辞不是稳定 API，但必须包含：

- 被加载文件的路径；
- 重复键的可读表示；
- 重复项的 1-based 行号和列号；
- 首次出现位置（强烈建议，同样使用 1-based 行号和列号）。

示意信息：

```text
Failed to load YAML config '.../portfolio.yaml': duplicate key 'weight_mode'
first defined at line 3, column 3; repeated at line 4, column 3
```

调用方不应依赖整段字符串完全相等，只应依赖异常类型和上述诊断信息的存在。

## 兼容性

- 合法 YAML 的解析结果不变。
- 过去依赖“最后一个重复键获胜”的 YAML 将不再被接受；这是有意的 bugfix，不提供兼容开关。
- `GPConfigManager` 的公共加载接口不变。
- 对外异常仍属于现有的 `ConfigValidationError`，不增加新的公共异常类型。
- 行为必须在 Windows 和 Linux 上一致；路径展示使用现有跨平台路径处理方式。

## 测试要求

至少增加以下自动化测试：

1. 顶层 mapping 的重复字符串键被拒绝。
2. 多层嵌套 mapping 的重复键被拒绝。
3. list 元素中的 mapping 重复键被拒绝。
4. `global_env.yaml` 中的重复键在 manager 初始化或加载该文件时被拒绝。
5. 不同 mapping 中的同名键可以正常加载。
6. 合法配置的加载结果与修复前一致。
7. 空文件、仅注释文件及根节点不是 mapping 的既有处理行为不变。
8. 对外异常为 `ConfigValidationError`，其 `__cause__` 为 YAML 解析异常。
9. 错误文本包含文件路径、重复键、重复项行列号；若实现记录首次位置，也验证首次位置。
10. Unicode 键的重复项能够被识别并正确显示。
11. YAML merge key 的既有合法行为不因本次修复改变。

## 验收标准

- 上述测试全部通过。
- `gpconfig` 现有测试套件全部通过。
- 所有经 `_load_yaml_dict()` 读取的 YAML 都执行重复显式键检查。
- 检查发生在转换为普通 `dict` 之前。
- 不含任何静默覆盖、自动修复或失败重试路径。
- 未使用不安全 YAML Loader。
- 合法配置的公共 API 和解析结果无回归。

## 对 Quant Types Portfolio 的影响

- Portfolio 模块不自行读取原始 YAML，也不直接依赖 PyYAML 来重复实现检查。
- Portfolio 配置加载沿用 `GPConfigManager` 的入口，并让上游 `ConfigValidationError` 原样传播。
- 待修复发布后，Quant Types 应把 `gpconfig` 的最低依赖版本提升到包含此修复的版本。
- 在最低依赖版本提升前，Portfolio 文档和测试不能宣称重复 YAML 键一定会被拒绝。
