import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
})

// ---- Dashboard ----
export const getDashboardSummary = () =>
  client.get('/api/dashboard/summary').then((r) => r.data)

// ---- Properties ----
export const getProperties = (params) =>
  client.get('/api/properties', { params }).then((r) => r.data)

export const getPropertyDetail = (propertyId) =>
  client.get(`/api/properties/${propertyId}`).then((r) => r.data)

export const getPropertyFilterOptions = () =>
  client.get('/api/properties/meta/filters').then((r) => r.data)

// ---- Leases ----
export const getLeases = (params) =>
  client.get('/api/leases', { params }).then((r) => r.data)

// ---- Data Quality ----
export const getDataQualityReport = () =>
  client.get('/api/data-quality').then((r) => r.data)

export const getDataQualityIssues = (params) =>
  client.get('/api/data-quality/issues', { params }).then((r) => r.data)

// ---- Risk ----
export const getRiskProperties = (params) =>
  client.get('/api/risk/properties', { params }).then((r) => r.data)

export const getPropertyRiskDetail = (propertyId) =>
  client.get(`/api/risk/properties/${propertyId}`).then((r) => r.data)

// ---- Analytics ----
export const getPortfolioAnalytics = () =>
  client.get('/api/analytics/portfolio').then((r) => r.data)

export const getRevenueAnalytics = () =>
  client.get('/api/analytics/revenue').then((r) => r.data)

export const getOccupancyAnalytics = () =>
  client.get('/api/analytics/occupancy').then((r) => r.data)

// ---- Forecast ----
export const getRevenueForecast = (params) =>
  client.get('/api/forecast/revenue', { params }).then((r) => r.data)

export const getOccupancyForecast = (params) =>
  client.get('/api/forecast/occupancy', { params }).then((r) => r.data)

// ---- CSV Import ----
export const uploadPropertiesCsv = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return client.post('/api/import/csv', formData).then((r) => r.data)
}

// ---- AI Insights ----
export const askInsightQuestion = (question) =>
  client.post('/api/insights/ask', { question }).then((r) => r.data)

export const getInsightExamples = () =>
  client.get('/api/insights/examples').then((r) => r.data)

export default client
