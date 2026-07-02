import { test, expect, type Page } from '@playwright/test'

// 是否启用需要后端服务的 e2e 测试。
// 默认跳过；设置环境变量 E2E_BACKEND=true 并启动后端后启用。
const BACKEND_AVAILABLE = process.env.E2E_BACKEND === 'true'

// 默认登录凭证（可通过环境变量覆盖）
const E2E_USERNAME = process.env.E2E_USERNAME ?? 'admin'
const E2E_PASSWORD = process.env.E2E_PASSWORD ?? 'change-me'

// 复用：通过 UI 完成登录，并等待跳转至 dashboard
async function loginViaUi(page: Page): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(E2E_USERNAME)
  await page.getByLabel('密码').fill(E2E_PASSWORD)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page).toHaveURL(/\/dashboard/)
}

test.describe('核心用户旅程 e2e', () => {
  // 登录页渲染 —— 不依赖后端
  test('登录页：渲染用户名/密码输入框与登录按钮', async ({ page }) => {
    // 未登录访问根路径会被 PrivateRoute 重定向到 /login
    await page.goto('/')
    await expect(page).toHaveURL(/\/login/)
    await expect(page.getByLabel('用户名')).toBeVisible()
    await expect(page.getByLabel('密码')).toBeVisible()
    await expect(page.getByRole('button', { name: '登录' })).toBeVisible()
  })

  // 404 页面 —— 不依赖后端
  test('404 页面：访问不存在的路径显示 404 与返回首页', async ({ page }) => {
    await page.goto('/this-route-does-not-exist')
    await expect(page.getByText('404', { exact: true })).toBeVisible()
    await expect(page.getByText('页面未找到')).toBeVisible()
    await expect(page.getByRole('link', { name: '返回首页' })).toBeVisible()
  })
})

// 以下测试需要后端服务运行：默认跳过，设置 E2E_BACKEND=true 后启用
test.describe('需要后端的核心旅程', () => {
  test.skip(!BACKEND_AVAILABLE, '需要后端服务运行（设置 E2E_BACKEND=true 并启动后端后启用）')

  // 登录流程：输入用户名密码 -> 点击登录 -> 跳转到 dashboard
  test('登录流程：输入凭证后跳转到 dashboard', async ({ page }) => {
    await loginViaUi(page)
    // 登录成功后顶部导航栏应可见
    await expect(page.getByRole('link', { name: '工作台' })).toBeVisible()
  })

  // 页面导航：点击各导航项 -> 验证页面加载（校验路由跳转）
  test('页面导航：点击各导航项加载对应页面', async ({ page }) => {
    await loginViaUi(page)

    // 覆盖对所有角色均可见的导航项
    const navCases = [
      { label: '财务报告', url: '/reports' },
      { label: '文档解析', url: '/documents' },
      { label: '智能问答', url: '/agent' },
      { label: '审计日志', url: '/audit' },
      { label: '工作台', url: '/dashboard' },
    ]

    for (const item of navCases) {
      await page.getByRole('link', { name: item.label }).click()
      await expect(page).toHaveURL(item.url)
    }
  })

  // 上传文档：登录后进入文档解析页 -> 上传文件 -> 文档列表更新
  test('上传文档：上传文件后文档列表出现该文档', async ({ page }) => {
    await loginViaUi(page)
    await page.getByRole('link', { name: '文档解析' }).click()
    await expect(page).toHaveURL('/documents')
    await expect(page.getByRole('heading', { name: '文档解析中心' })).toBeVisible()

    const fileName = `e2e-upload-${Date.now()}.csv`
    await page.locator('input[type=file]').setInputFiles({
      name: fileName,
      mimeType: 'text/csv',
      buffer: Buffer.from('date,revenue\n2025-01-01,1000\n'),
    })
    await page.getByRole('button', { name: '上传并解析' }).click()

    // 文档列表更新，出现刚上传的文件名
    await expect(page.getByText(fileName).first()).toBeVisible()
  })

  // 生成报告：登录后进入财务报告页 -> 创建报告 -> 列表更新并显示状态
  test('生成报告：创建报告后报告列表更新并显示状态', async ({ page }) => {
    await loginViaUi(page)
    await page.getByRole('link', { name: '财务报告' }).click()
    await expect(page).toHaveURL('/reports')
    await expect(page.getByRole('heading', { name: '财务报告中心' })).toBeVisible()

    const reportTitle = `e2e 报告 ${Date.now()}`
    await page.getByRole('textbox').fill(reportTitle)
    await page.getByRole('spinbutton').fill('2025')
    await page.getByRole('combobox').nth(0).selectOption('profit')
    await page.getByRole('combobox').nth(1).selectOption('Q2')
    await page.getByRole('button', { name: '创建报告' }).click()

    // 报告列表更新，新报告出现在列表中
    const reportRow = page.getByRole('row').filter({ hasText: reportTitle }).first()
    await expect(reportRow).toBeVisible()
    // 状态徽章显示已知状态之一
    await expect(
      reportRow.getByText(/草稿|待处理|生成中|待复核|已通过|已驳回|审核中/).first(),
    ).toBeVisible()
  })

  // 审批：登录后进入人工审批页 -> 对待审批报告执行通过 -> 该报告移出待审批列表
  test('审批：对待审批报告执行通过后该报告移出待审批列表', async ({ page }) => {
    await loginViaUi(page)
    await page.getByRole('link', { name: '人工审批' }).click()
    await expect(page).toHaveURL('/approvals')
    await expect(page.getByRole('heading', { name: '人工审批' })).toBeVisible()

    // 等待待审批列表加载（表格出现表示有待审批数据）
    await expect(page.getByRole('table')).toBeVisible()

    // 取第一行待审批报告（nth(0) 为表头）
    const approvalRow = page.getByRole('row').nth(1)
    await expect(approvalRow).toBeVisible()
    const titleCell = approvalRow.locator('td').first()
    await expect(titleCell).not.toBeEmpty()
    const reportTitle = (await titleCell.textContent()) ?? ''
    expect(reportTitle.trim().length).toBeGreaterThan(0)

    await approvalRow.getByRole('button', { name: '通过' }).click()

    // 通过后该报告状态变更，不再出现在待审批列表中
    await expect(page.getByRole('row').filter({ hasText: reportTitle.trim() })).toHaveCount(0)
  })

  // 智能问答：登录后进入智能问答页 -> 发送消息 -> 收到智能体回复
  test('智能问答：发送消息后收到智能体回复', async ({ page }) => {
    await loginViaUi(page)
    await page.getByRole('link', { name: '智能问答' }).click()
    await expect(page).toHaveURL('/agent')
    await expect(page.getByRole('heading', { name: '智能问答' })).toBeVisible()

    const question = 'e2e 测试问题：本月毛利率是多少？'
    await page.getByPlaceholder('请输入问题...').fill(question)
    await page.getByRole('button', { name: '发送' }).click()

    // 用户消息出现在对话区
    await expect(page.getByText(question).first()).toBeVisible()
    // 等待智能体返回（输入框在 loading 时被禁用，返回后重新启用）
    await expect(page.getByPlaceholder('请输入问题...')).toBeEnabled()
    // 智能体回复气泡出现且非空
    const agentReply = page.locator('.chat-message.agent .chat-bubble').last()
    await expect(agentReply).not.toBeEmpty()
  })
})
