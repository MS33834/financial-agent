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
})
