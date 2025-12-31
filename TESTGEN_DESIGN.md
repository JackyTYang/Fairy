# 智能GUI测试生成系统设计方案

## 1. 研究动机与问题定义

### 1.1 核心问题

尽管自动化 GUI 测试技术已取得长足进步，但在面对现代 APP 复杂的业务逻辑时，现有的主流方法仍存在显著局限性。这些局限性主要体现在无法处理跨页面的深层依赖关系以及复杂的交互操作，导致测试往往停留在浅层页面，无法触达核心功能。

### 1.2 典型场景

#### 场景1：跨页面的参数与状态依赖（Deep Dependency）

**案例**：电商应用"使用满减优惠券"功能

用户必须依次完成一系列严格受限的操作：
1. 在商品详情页选择**有库存**的规格（参数依赖）
2. 在购物车添加商品直至总金额**满足阈值**（如满 100 元，状态依赖）
3. 最后在结算页才能看到并选择优惠券

**现有工具的问题**：
- 传统的随机或遍历工具因缺乏对"金额"和"库存"语义的理解
- 往往在第一步就因随机选择缺货商品而阻塞
- 或因金额不足而无法触发优惠券逻辑
- 导致该核心业务路径永远无法被覆盖

#### 场景2：隐式交互与复杂手势（Complex Interaction）

**案例**：笔记或邮件应用的隐藏功能

核心功能（如"归档"、"删除"或"多选"）往往隐藏在特定的手势操作之后：
- 向左滑动列表项
- 长按某个区域

**现有工具的问题**：
- 大多仅支持显式的点击（Click）操作
- 对于此类隐式交互缺乏探索机制
- 导致大量功能点被遗漏

### 1.3 本质问题

> **工具不懂业务，只懂控件**

现有工具缺乏：
- 对操作、参数、页面及状态之间**深层依赖关系**的挖掘能力
- 无法生成覆盖多种触发场景（包括复杂手势与边界条件）的丰富测试用例

### 1.4 研究目标

引入大语言模型（LLM）的强大推理能力，设计一种智能化的 GUI 测试代理（Agent）。该 Agent 应具备：
- 类似人类的逻辑思维
- 主动分析界面语义
- 挖掘操作间的因果依赖
- 规划出能覆盖深层业务逻辑和复杂交互的有效测试路径

---

## 2. 系统架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│           智能GUI测试系统（基于LLM Agent）                │
└─────────────────────────────────────────────────────────┘

Phase 1: 功能探索（已实现 ✓）
├─ Explorer: 主动探索APP功能
├─ Perceptor: 屏幕感知（SoM标记）
├─ Executor: 执行动作（点击、滑动、长按）
└─ 输出: feature_tree_compressed.json
         ├─ 功能列表（features）
         ├─ 状态转换（states + transitions）
         └─ 操作步骤（steps）

                    ↓

Phase 2: 依赖分析（新增 🆕）
├─ DependencyAnalyzer: 依赖关系挖掘Agent
│  ├─ 参数依赖（如：stock > 0）
│  ├─ 状态依赖（如：cart_total >= 100）
│  └─ 序列依赖（如：优惠券必须在加购后）
├─ ConstraintExtractor: 约束提取
│  ├─ 从UI提取（输入框格式、数值范围）
│  └─ 从探索历史提取（失败模式分析）
└─ 输出: dependency_graph.json
         └─ 每个功能的前置条件和约束

                    ↓

Phase 3: 测试规划（新增 🆕）
├─ TestPlannerAgent: 智能测试规划Agent
│  ├─ 识别核心功能（业务价值排序）
│  ├─ 规划依赖路径（如何到达深层功能）
│  └─ 制定覆盖策略（正向、边界、异常）
└─ 输出: test_plan.json
         ├─ 测试优先级
         ├─ 前置步骤路径
         └─ 覆盖目标

                    ↓

Phase 4: 用例生成（新增 🆕）
├─ TestCaseGenerator: 测试用例生成器
│  ├─ 路径拼接（从feature_tree提取）
│  ├─ 数据生成（调用ConstraintSolver）
│  └─ 预期结果推断
├─ ConstraintSolver: 约束求解器（LLM驱动）
│  ├─ 生成满足约束的测试数据
│  └─ 生成边界和异常数据
└─ 输出: test_suite.json
         ├─ 测试用例（含步骤序列）
         ├─ 测试数据
         └─ 预期结果

                    ↓

Phase 5: 执行与验证（复用 + 增强）
├─ Executor: 执行测试用例（已有）
├─ TestOracle: 结果验证（新增）
│  ├─ 对比预期结果
│  └─ 记录覆盖情况
└─ 输出: test_report.json
         ├─ 通过/失败用例
         ├─ 功能覆盖率
         └─ 依赖覆盖率
```

### 2.2 架构特点

#### 探索与测试分离
- **Explorer**：只负责了解功能和依赖，不做测试
- **Test Generator**：基于探索结果，智能生成测试

#### 依赖关系显式化
- 传统工具：不知道功能间的依赖
- 本方案：显式提取并存储依赖关系

#### LLM多阶段应用
- **阶段1（探索）**：理解UI，规划探索
- **阶段2（分析）**：提取依赖关系
- **阶段3（规划）**：制定测试策略
- **阶段4（生成）**：生成测试数据

#### 覆盖深层依赖
- 自动识别"需要多步前置"的功能
- 规划完整的前置路径
- 生成满足依赖的测试数据

---

## 3. 关键模块设计

### 3.1 DependencyAnalyzer（依赖分析Agent）🆕

#### 功能定位

从探索记录中挖掘功能间的依赖关系

#### 核心能力

1. **参数依赖**：某功能需要特定参数值（如：库存>0）
2. **状态依赖**：某功能需要特定状态（如：金额>=100）
3. **序列依赖**：某功能必须在其他功能之后（如：结算需要先加购）

#### 接口设计

```python
class DependencyAnalyzer:
    """依赖关系分析Agent

    使用LLM分析feature_tree，提取：
    1. 参数依赖：某功能需要特定参数值（如：库存>0）
    2. 状态依赖：某功能需要特定状态（如：金额>=100）
    3. 序列依赖：某功能必须在其他功能之后（如：结算需要先加购）
    """

    async def analyze(
        self,
        feature_tree: FeatureTree
    ) -> DependencyGraph:
        """分析依赖关系"""

        # 为每个功能构建分析prompt
        for feature in feature_tree.features:
            prompt = f"""
            分析以下功能的前置条件和依赖关系：

            功能：{feature.name}
            描述：{feature.description}

            探索路径：
            {self._format_paths_to_feature(feature_tree, feature)}

            请分析：
            1. 这个功能需要满足什么条件才能触发？
            2. 需要先完成哪些前置功能？
            3. 需要什么样的输入参数？

            输出JSON格式的依赖关系。
            """

            dependency = await self.llm.analyze(prompt)
            # 解析并存储依赖关系
```

#### 输出示例（dependency_graph.json）

```json
{
  "features": {
    "使用优惠券": {
      "dependencies": {
        "state": [
          {
            "condition": "cart_total >= 100",
            "description": "购物车总金额需大于等于100元"
          }
        ],
        "sequence": [
          {
            "prerequisite": "加入购物车",
            "reason": "必须先有商品才能使用优惠券"
          }
        ],
        "parameter": [
          {
            "name": "商品规格",
            "constraint": "stock > 0",
            "description": "选择的规格必须有库存"
          }
        ]
      }
    }
  }
}
```

---

### 3.2 TestPlannerAgent（测试规划Agent）🆕

#### 功能定位

基于依赖关系，智能规划测试策略

#### 核心能力

1. 识别核心功能（业务价值高）
2. 规划依赖路径（如何到达深层功能）
3. 制定覆盖策略（正向、边界、异常）

#### 接口设计

```python
class TestPlannerAgent:
    """测试规划Agent

    基于LLM的智能规划：
    1. 识别核心功能（业务价值高）
    2. 规划依赖路径（如何到达深层功能）
    3. 制定覆盖策略（正向、边界、异常）
    """

    async def plan(
        self,
        feature_tree: FeatureTree,
        dependency_graph: DependencyGraph,
        coverage_goals: Dict[str, Any]
    ) -> TestPlan:
        """生成测试计划"""

        prompt = f"""
        你是一个测试专家。根据以下信息制定测试计划：

        ## 功能列表
        {self._format_features(feature_tree)}

        ## 依赖关系
        {dependency_graph.to_prompt_text()}

        ## 覆盖目标
        - 功能覆盖：所有核心功能至少测试1次
        - 路径覆盖：覆盖主要业务路径
        - 边界覆盖：关键参数的边界值

        ## 任务
        1. 识别核心业务功能（如：支付、优惠券、下单）
        2. 对于有深层依赖的功能，规划完整的前置步骤序列
        3. 为每个功能设计3类测试：
           - 正向测试（满足所有条件）
           - 边界测试（边界值）
           - 异常测试（不满足某个条件）

        输出JSON格式的测试计划。
        """

        plan = await self.llm.plan(prompt)
        return TestPlan.from_dict(plan)
```

#### 输出示例（test_plan.json）

```json
{
  "test_items": [
    {
      "feature": "使用优惠券",
      "priority": "high",
      "business_value": "核心交易功能",

      "prerequisite_path": [
        "首页",
        "商品详情页",
        "选择商品规格（有库存）",
        "加入购物车（凑够金额）",
        "购物车页面",
        "结算页"
      ],

      "test_scenarios": [
        {
          "type": "positive",
          "name": "正常使用优惠券",
          "description": "满足所有条件，成功使用优惠券",
          "constraints": {
            "cart_total": 150,
            "stock": 10,
            "coupon_available": true
          },
          "expected_result": "优惠券成功应用，金额减少"
        },
        {
          "type": "boundary",
          "name": "刚好满足金额阈值",
          "description": "金额刚好等于100元",
          "constraints": {
            "cart_total": 100.00
          },
          "expected_result": "优惠券可用"
        },
        {
          "type": "negative",
          "name": "金额不足",
          "description": "购物车金额未达到阈值",
          "constraints": {
            "cart_total": 99.99
          },
          "expected_result": "优惠券不可用，提示金额不足"
        },
        {
          "type": "negative",
          "name": "商品缺货",
          "description": "选择的规格无库存",
          "constraints": {
            "stock": 0
          },
          "expected_result": "无法加入购物车"
        }
      ]
    }
  ]
}
```

---

### 3.3 TestCaseGenerator（测试用例生成器）🆕

#### 功能定位

基于测试计划生成可执行的测试用例

#### 核心能力

1. 路径提取（从feature_tree）
2. 步骤序列生成
3. 测试数据生成
4. 预期结果推断

#### 接口设计

```python
class TestCaseGenerator:
    """测试用例生成器

    输入：测试计划 + 功能树
    输出：完整的测试用例（步骤序列 + 测试数据 + 预期结果）
    """

    async def generate(
        self,
        test_plan: TestPlan,
        feature_tree: FeatureTree
    ) -> TestSuite:
        """生成测试套件"""

        test_suite = TestSuite()

        for test_item in test_plan.test_items:
            # 1. 从feature_tree中提取到达该功能的路径
            path_steps = self._extract_path_from_tree(
                feature_tree,
                test_item.prerequisite_path
            )

            # 2. 为每个测试场景生成用例
            for scenario in test_item.test_scenarios:
                # 3. 生成满足约束的测试数据
                test_data = await self.constraint_solver.solve(
                    scenario.constraints
                )

                # 4. 构建完整测试用例
                test_case = TestCase(
                    id=f"TC_{test_item.feature}_{scenario.type}_{uuid4()}",
                    name=scenario.name,
                    description=scenario.description,

                    # 步骤序列（从feature_tree提取）
                    steps=path_steps,

                    # 测试数据（LLM生成）
                    test_data=test_data,

                    # 预期结果
                    expected_result=scenario.expected_result,

                    # 元数据
                    feature=test_item.feature,
                    priority=test_item.priority,
                    type=scenario.type
                )

                test_suite.add(test_case)

        return test_suite
```

#### 输出示例（test_suite.json）

```json
{
  "test_cases": [
    {
      "id": "TC_使用优惠券_positive_001",
      "name": "正常使用优惠券",
      "feature": "使用优惠券",
      "type": "positive",
      "priority": "high",

      "steps": [
        {
          "step_id": 1,
          "action": "tap",
          "target": "商品列表中的第一个商品",
          "description": "进入商品详情页"
        },
        {
          "step_id": 2,
          "action": "tap",
          "target": "规格选择按钮",
          "description": "打开规格选择弹窗"
        },
        {
          "step_id": 3,
          "action": "select",
          "target": "颜色：红色，尺寸：L",
          "data": {
            "color": "红色",
            "size": "L"
          },
          "constraints": {
            "stock": "> 0"
          },
          "description": "选择有库存的规格"
        },
        {
          "step_id": 4,
          "action": "input",
          "target": "数量输入框",
          "data": {
            "quantity": 2
          },
          "description": "输入购买数量（单价50，凑够100元）"
        },
        {
          "step_id": 5,
          "action": "tap",
          "target": "加入购物车按钮",
          "description": "加入购物车"
        },
        {
          "step_id": 6,
          "action": "tap",
          "target": "购物车图标",
          "description": "进入购物车页面"
        },
        {
          "step_id": 7,
          "action": "tap",
          "target": "去结算按钮",
          "description": "进入结算页"
        },
        {
          "step_id": 8,
          "action": "tap",
          "target": "优惠券选择区域",
          "description": "打开优惠券列表"
        },
        {
          "step_id": 9,
          "action": "tap",
          "target": "满100减10优惠券",
          "description": "选择优惠券"
        }
      ],

      "test_data": {
        "product": {
          "id": "P001",
          "name": "测试商品",
          "price": 50.00,
          "color": "红色",
          "size": "L",
          "stock": 10
        },
        "quantity": 2,
        "coupon": {
          "id": "C001",
          "name": "满100减10",
          "threshold": 100.00,
          "discount": 10.00
        }
      },

      "expected_result": {
        "order_total": 90.00,
        "coupon_applied": true,
        "final_price": 90.00
      }
    }
  ]
}
```

---

### 3.4 ConstraintSolver（约束求解器）🆕

#### 功能定位

自动生成满足约束的测试数据

#### 核心能力

1. 根据约束条件生成满足条件的测试数据
2. 生成边界值数据
3. 生成异常数据（不满足约束）

#### 接口设计

```python
class ConstraintSolver:
    """约束求解器（LLM驱动）

    根据约束条件生成满足条件的测试数据
    """

    async def solve(self, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """求解约束，生成测试数据"""

        prompt = f"""
        生成满足以下约束的测试数据：

        约束条件：
        {json.dumps(constraints, ensure_ascii=False, indent=2)}

        要求：
        1. 数据必须满足所有约束
        2. 数据应该真实合理（如：价格不能是负数）
        3. 如果约束有范围，选择典型值

        示例：
        约束：cart_total >= 100, stock > 0
        数据：
        {{
          "product_price": 50.00,
          "quantity": 2,
          "stock": 10
        }}

        请输出JSON格式的测试数据。
        """

        test_data = await self.llm.generate(prompt)
        return test_data
```

---

## 4. 实现路线图

### 第一阶段：基础依赖分析（2-3周）

**目标**：能够识别简单的依赖关系

#### 任务清单

1. **实现 `DependencyAnalyzer`**
   - [ ] 从feature_tree提取功能和路径
   - [ ] 使用LLM分析每个功能的前置条件
   - [ ] 输出dependency_graph.json

2. **实现 `TestPlannerAgent`（简化版）**
   - [ ] 只生成正向测试计划
   - [ ] 基于dependency规划前置路径

3. **验证效果**
   - [ ] 在电商APP上测试（优惠券场景）
   - [ ] 验证是否能识别"金额>=100"的依赖

#### 交付物

- `dependency_graph.json` - 依赖关系文件
- `test_plan.json` - 初步测试计划
- 验证报告

---

### 第二阶段：测试用例生成（3-4周）

**目标**：自动生成可执行的测试用例

#### 任务清单

1. **实现 `TestCaseGenerator`**
   - [ ] 路径提取（从feature_tree）
   - [ ] 步骤序列生成
   - [ ] 与Executor对接

2. **实现 `ConstraintSolver`（简化版）**
   - [ ] 使用LLM生成满足约束的测试数据
   - [ ] 处理简单约束（数值范围、选项选择）

3. **执行与验证**
   - [ ] 自动执行生成的测试用例
   - [ ] 记录执行结果

#### 交付物

- `test_suite.json` - 测试用例套件
- `test_execution_report.json` - 执行报告
- 功能覆盖率报告

---

### 第三阶段：边界与异常测试（2-3周）

**目标**：生成边界值和异常测试

#### 任务清单

1. **增强 `TestPlannerAgent`**
   - [ ] 自动识别边界条件
   - [ ] 生成异常测试场景

2. **增强 `ConstraintSolver`**
   - [ ] 生成边界值（如：99.99, 100.00, 100.01）
   - [ ] 生成不满足约束的数据

3. **覆盖率分析**
   - [ ] 功能覆盖率
   - [ ] 依赖覆盖率
   - [ ] 路径覆盖率

#### 交付物

- 完整的测试套件（正向+边界+异常）
- 覆盖率报告
- 论文实验数据

---

## 5. 项目结构

```
Fairy/
├── Explorer/          # 已有：功能探索
│   ├── explorer.py
│   ├── planner.py
│   ├── entities.py
│   └── feature_tree_builder.py
│
├── Executor/          # 已有：动作执行
│   ├── executor.py
│   ├── config.py
│   └── output.py
│
├── Perceptor/         # 已有：屏幕感知
│   └── (在Fairy/tools/screen_perceptor/)
│
├── TestGen/           # 🆕 新增：测试生成
│   ├── __init__.py
│   ├── dependency_analyzer.py    # 依赖分析Agent
│   ├── test_planner.py           # 测试规划Agent
│   ├── test_case_generator.py   # 用例生成器
│   ├── constraint_solver.py      # 约束求解器
│   ├── test_oracle.py            # 测试预言（验证）
│   ├── entities.py               # 实体定义
│   │   ├── DependencyGraph       # 依赖图
│   │   ├── TestPlan              # 测试计划
│   │   ├── TestCase              # 测试用例
│   │   ├── TestSuite             # 测试套件
│   │   └── TestReport            # 测试报告
│   └── prompts/                  # LLM Prompts
│       ├── dependency_analysis.py
│       ├── test_planning.py
│       └── constraint_solving.py
│
└── integration/       # 集成示例
    ├── explorer_example.py       # 已有
    └── testgen_example.py        # 🆕 新增
```

---

## 6. 核心创新点

### 6.1 探索与测试分离

**传统方法**：边探索边测试，缺乏全局视角

**本方案**：
- **Explorer**：先完整探索，建立功能地图
- **TestGen**：基于功能地图，智能规划测试

**优势**：
- 避免盲目测试
- 能够规划复杂的前置路径
- 覆盖更深层的功能

---

### 6.2 依赖关系显式化

**传统方法**：工具不知道功能间的依赖关系

**本方案**：
- 使用LLM分析并提取依赖关系
- 显式存储在dependency_graph中
- 测试规划时利用依赖信息

**优势**：
- 能够识别"需要多步前置"的功能
- 自动规划前置路径
- 生成满足依赖的测试数据

---

### 6.3 LLM多阶段应用

**阶段1（探索 - Explorer）**：
- 理解UI语义
- 规划探索策略
- 识别功能边界

**阶段2（分析 - DependencyAnalyzer）**：
- 分析功能依赖
- 提取约束条件
- 识别关键参数

**阶段3（规划 - TestPlanner）**：
- 评估业务价值
- 规划测试策略
- 设计测试场景

**阶段4（生成 - TestCaseGenerator）**：
- 生成测试数据
- 求解约束条件
- 推断预期结果

**优势**：
- 每个阶段专注于特定任务
- LLM能力充分发挥
- 更高的准确性和覆盖率

---

### 6.4 覆盖深层依赖

**问题场景**：电商优惠券需要"有库存规格" + "金额>=100"

**传统工具**：
- 随机选择，往往失败
- 无法理解"金额"语义
- 无法规划前置路径

**本方案**：
1. **DependencyAnalyzer** 识别依赖：
   - stock > 0
   - cart_total >= 100
   - sequence: 加购 → 结算 → 优惠券

2. **TestPlanner** 规划路径：
   - 选择有库存的商品
   - 凑够100元（2个50元商品）
   - 进入结算页
   - 选择优惠券

3. **ConstraintSolver** 生成数据：
   - product_price: 50.00
   - quantity: 2
   - stock: 10

4. **TestCaseGenerator** 生成用例：
   - 完整的步骤序列
   - 满足约束的测试数据
   - 预期结果：90.00元

**优势**：
- 能够触达深层功能
- 覆盖复杂的业务场景
- 自动生成有效的测试数据

---

## 7. 预期成果

### 7.1 学术贡献

1. **创新的测试生成方法**
   - 基于LLM的依赖分析
   - 智能测试规划
   - 约束求解驱动的数据生成

2. **实验验证**
   - 在多个真实APP上验证
   - 与现有工具对比（覆盖率、深度）
   - 统计分析

3. **开源工具**
   - 完整的实现
   - 可复现的实验
   - 社区贡献

---

### 7.2 实用价值

1. **提高测试覆盖率**
   - 触达深层功能（如：优惠券、支付）
   - 覆盖隐藏交互（如：手势操作）

2. **减少人工成本**
   - 自动识别依赖关系
   - 自动规划测试路径
   - 自动生成测试数据

3. **发现更多缺陷**
   - 边界值测试
   - 异常场景测试
   - 复杂路径测试

---

## 8. 风险与挑战

### 8.1 技术挑战

1. **依赖识别准确性**
   - LLM可能误判依赖
   - 需要验证机制

2. **约束求解复杂性**
   - 某些约束可能无解
   - 需要回退机制

3. **执行稳定性**
   - 动态UI可能导致执行失败
   - 需要重试和恢复机制

### 8.2 应对策略

1. **人工验证**
   - 关键依赖人工review
   - 迭代优化prompt

2. **混合求解**
   - LLM + 规则引擎
   - 分层求解（简单约束优先）

3. **鲁棒性增强**
   - 动态定位（基于语义而非位置）
   - 错误恢复机制

---

## 9. 下一步行动

### 立即开始

1. **创建TestGen模块**
   ```bash
   mkdir -p Fairy/TestGen/{prompts,entities}
   touch Fairy/TestGen/__init__.py
   ```

2. **实现DependencyAnalyzer**
   - 编写实体类（Dependency, DependencyGraph）
   - 实现分析逻辑
   - 设计prompt

3. **在电商APP上验证**
   - 先用Explorer探索
   - 再用DependencyAnalyzer分析
   - 检验依赖识别效果

### 后续计划

1. **第一阶段（2-3周）**：依赖分析
2. **第二阶段（3-4周）**：用例生成
3. **第三阶段（2-3周）**：边界与异常测试
4. **论文撰写**：与实现并行

---

## 10. 参考资料

### 相关工作

1. **GUI测试工具**
   - Monkey（随机测试）
   - UIAutomator（基于控件）
   - Appium（脚本驱动）

2. **基于模型的测试**
   - FSM-based testing
   - Model-based test generation

3. **LLM在软件测试中的应用**
   - CodeT5 for test generation
   - GPT for test case generation

### 待研究

1. 依赖关系表示的最佳形式
2. 约束求解的高效算法
3. 覆盖率度量方法