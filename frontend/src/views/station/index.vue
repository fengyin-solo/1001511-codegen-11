<template>
  <section class="page" data-module="station">
    <header class="page-head">
      <div>
        <h2>观测站点管理</h2>
        <p class="page-desc">维护观测站点，围绕站点编码、站点名称、站点类别、经纬度坐标做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记观测站点</button>
        <button class="btn" type="button" @click="exportRows">导出观测站点清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label v-for="field in filterFields" :key="field.key" class="filter-item">
        <span>{{ field.label }}</span>
        <input v-model="filters[field.key]" :placeholder="field.placeholder" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyHint }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条观测站点记录</span>
      <div class="pager">
        <button class="btn ghost" type="button" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
        <span class="page-info">第 {{ page }} / {{ pageCount }} 页</span>
        <button class="btn ghost" type="button" :disabled="page >= pageCount" @click="goPage(page + 1)">下一页</button>
      </div>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type FilterKey = 'code' | 'name' | 'category'

const ENDPOINT = '/api/station'
const columns = ["站点编码", "站点名称", "站点类别", "经纬度坐标", "海拔高度", "建站年份", "值守方式", "站点状态"]
const actions = ["办理入网", "标记降级", "停用站点"]
const statuses = ["待入网", "正常运行", "降级运行", "已停用"]
const stats = [{"label": "在网站点", "value": 0}, {"label": "降级站点", "value": 0}, {"label": "停用站点", "value": 0}]

const filterFields: { key: FilterKey; label: string; placeholder: string }[] = [
  { key: 'code', label: '站点编码', placeholder: '精确匹配，如 STAT-0001' },
  { key: 'name', label: '站点名称', placeholder: '按站点名称检索' },
  { key: 'category', label: '站点类别', placeholder: '按站点类别检索' },
]

// 站点编码写法：2-6 位字母 + 短横线 + 4 位数字，与后端口径一致。
const CODE_PATTERN = /^[A-Za-z]{2,6}-\d{4}$/
const CODE_FORMAT_HINT = '站点编码写法不对：应为「字母-四位数字」，例如 STAT-0001'

const STATE_KEY = 'station:list-state'
const PAGE_SIZE = 10

const rows = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const errorMessage = ref('')
const filters = ref<Record<FilterKey, string>>({ code: '', name: '', category: '' })

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const hasActiveFilters = computed(() =>
  Boolean(filters.value.code.trim() || filters.value.name.trim() || filters.value.category.trim()),
)
const emptyHint = computed(() =>
  hasActiveFilters.value
    ? '当前筛选条件下没有匹配的观测站点，可调整条件后重新查询'
    : '暂无观测站点数据，可先登记观测站点',
)

function persistState() {
  sessionStorage.setItem(STATE_KEY, JSON.stringify({ filters: filters.value, page: page.value }))
}

function restoreState() {
  try {
    const saved = sessionStorage.getItem(STATE_KEY)
    if (!saved) return
    const state = JSON.parse(saved) as { filters?: Record<FilterKey, string>; page?: number }
    filters.value = { code: '', name: '', category: '', ...state.filters }
    page.value = Math.max(1, Number(state.page) || 1)
  } catch {
    sessionStorage.removeItem(STATE_KEY)
  }
}

function validateFilters(): boolean {
  const code = filters.value.code.trim()
  if (code && !CODE_PATTERN.test(code)) {
    errorMessage.value = `${CODE_FORMAT_HINT}（当前填写：${code}）`
    return false
  }
  return true
}

function activeParams(): URLSearchParams {
  const params = new URLSearchParams()
  if (filters.value.code.trim()) params.set('code', filters.value.code.trim())
  if (filters.value.name.trim()) params.set('name', filters.value.name.trim())
  if (filters.value.category.trim()) params.set('category', filters.value.category.trim())
  return params
}

function applyFilters() {
  page.value = 1
  void reload()
}

function resetFilters() {
  filters.value = { code: '', name: '', category: '' }
  page.value = 1
  void reload()
}

function goPage(target: number) {
  page.value = Math.min(Math.max(1, target), pageCount.value)
  void reload()
}

function exportRows() {
  if (!validateFilters()) return
  const params = activeParams()
  const query = params.toString()
  window.open(`${ENDPOINT}/export${query ? `?${query}` : ''}`, '_blank')
}

function openCreate() {
  errorMessage.value = '观测站点登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('观测站点动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '观测站点操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  if (!validateFilters()) return
  const params = activeParams()
  params.set('page', String(page.value))
  params.set('size', String(PAGE_SIZE))
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      const detail = await response.json().then((body) => body?.detail).catch(() => null)
      throw new Error(typeof detail === 'string' ? detail : '观测站点列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    persistState()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '观测站点列表读取失败'
  }
}

onMounted(() => {
  restoreState()
  void reload()
})
</script>
