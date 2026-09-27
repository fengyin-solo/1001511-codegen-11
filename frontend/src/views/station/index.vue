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

    <form class="filter-bar" @submit.prevent="search">
      <label v-for="field in filterFields" :key="field.key" class="filter-item">
        <span>{{ field.label }}</span>
        <input v-model="filters[field.key]" :placeholder="`按${field.label}检索`" />
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
        <span>第 {{ page }} / {{ pageCount }} 页</span>
        <button class="btn ghost" type="button" :disabled="page >= pageCount" @click="goPage(page + 1)">下一页</button>
      </div>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type FilterKey = 'code' | 'name' | 'category'

const ENDPOINT = '/api/station'
const columns = ["站点编码", "站点名称", "站点类别", "经纬度坐标", "海拔高度", "建站年份", "值守方式", "站点状态"]
const actions = ["办理入网", "标记降级", "停用站点"]
const statuses = ["待入网", "正常运行", "降级运行", "已停用"]
const stats = [{"label": "在网站点", "value": 0}, {"label": "降级站点", "value": 0}, {"label": "停用站点", "value": 0}]

const PAGE_SIZE = 10
const STORAGE_KEY = 'station-list-state'
// 与后端同一口径：字母前缀 + 短横线 + 数字序号，例如 STAT-0001
const CODE_PATTERN = /^[A-Za-z]+-\d+$/

const route = useRoute()
const router = useRouter()

const rows = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const errorMessage = ref('')
const filters = ref<Record<FilterKey, string>>({ code: '', name: '', category: '' })
const filterFields: { key: FilterKey; label: string }[] = [
  { key: 'code', label: '站点编码' },
  { key: 'name', label: '站点名称' },
  { key: 'category', label: '站点类别' },
]

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const hasActiveFilter = computed(() => Object.values(filters.value).some((value) => value.trim() !== ''))
const emptyHint = computed(() =>
  hasActiveFilter.value
    ? '没有符合当前筛选条件的观测站点，请调整站点编码、站点名称或站点类别后重新查询'
    : '暂无观测站点数据，可先登记观测站点',
)

function asText(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function validateFilters(): boolean {
  const code = filters.value.code.trim()
  if (code && !CODE_PATTERN.test(code)) {
    errorMessage.value = `站点编码写法不对：应为「字母-数字」组合，例如 STAT-0001；当前「站点编码」填的是「${code}」，请改正后再查询`
    return false
  }
  errorMessage.value = ''
  return true
}

function activeParams(): Record<string, string> {
  const params: Record<string, string> = {}
  if (filters.value.code.trim()) params.code = filters.value.code.trim()
  if (filters.value.name.trim()) params.name = filters.value.name.trim()
  if (filters.value.category.trim()) params.category = filters.value.category.trim()
  return params
}

function queryFromState(): Record<string, string> {
  const query = activeParams()
  if (page.value > 1) query.page = String(page.value)
  return query
}

function sameAsRoute(query: Record<string, string>): boolean {
  const keys = new Set([...Object.keys(query), ...Object.keys(route.query)])
  return [...keys].every((key) => asText(route.query[key]) === (query[key] ?? ''))
}

function saveState() {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ ...filters.value, page: page.value }))
}

function restoreState(): boolean {
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? '') as Record<string, unknown>
    filters.value = {
      code: asText(saved.code),
      name: asText(saved.name),
      category: asText(saved.category),
    }
    const savedPage = Number(saved.page)
    page.value = Number.isInteger(savedPage) && savedPage > 0 ? savedPage : 1
    return true
  } catch {
    return false
  }
}

function applyQuery(query: Record<string, unknown>) {
  filters.value = { code: asText(query.code), name: asText(query.name), category: asText(query.category) }
  const queryPage = Number(query.page)
  page.value = Number.isInteger(queryPage) && queryPage > 0 ? queryPage : 1
}

/** 状态变更后统一走这里：写 URL、存 sessionStorage，翻页离开再回来都能留住条件与页码。 */
function commitState() {
  saveState()
  const query = queryFromState()
  if (sameAsRoute(query)) {
    void reload()
  } else {
    void router.replace({ query })
  }
}

function search() {
  if (!validateFilters()) return
  page.value = 1
  commitState()
}

function resetFilters() {
  filters.value = { code: '', name: '', category: '' }
  page.value = 1
  errorMessage.value = ''
  commitState()
}

function goPage(target: number) {
  if (target < 1 || target > pageCount.value || target === page.value) return
  page.value = target
  commitState()
}

function exportRows() {
  if (!validateFilters()) return
  const params = new URLSearchParams(activeParams()).toString()
  window.open(`${ENDPOINT}/export${params ? `?${params}` : ''}`, '_blank')
}

function openCreate() {
  errorMessage.value = '观测站点登记入口尚未接入审批流'
}

async function readDetail(response: Response): Promise<string | null> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    return typeof body.detail === 'string' ? body.detail : null
  } catch {
    return null
  }
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
  const params = new URLSearchParams(activeParams())
  params.set('page', String(page.value))
  params.set('size', String(PAGE_SIZE))
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error((await readDetail(response)) ?? '观测站点列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '观测站点列表读取失败'
  }
}

onMounted(() => {
  const hasQueryState = ['code', 'name', 'category', 'page'].some((key) => key in route.query)
  if (hasQueryState) {
    applyQuery(route.query)
  } else {
    restoreState()
  }
  void reload()
})

watch(
  () => route.query,
  (query) => {
    applyQuery(query)
    saveState()
    void reload()
  },
)
</script>
