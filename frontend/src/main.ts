import { createApp } from 'vue'
import { Quasar, Notify, Dialog, ClosePopup } from 'quasar'
import { QCheckbox, QDialog, QCardActions, QMarkupTable, QBadge, QBanner, QBreadcrumbs, QBreadcrumbsEl, QBtn, QCard, QCardSection, QChip, QExpansionItem, QFooter, QHeader, QIcon, QInput, QItem, QItemLabel, QItemSection, QLayout, QLinearProgress, QList, QPage, QPageContainer, QSelect, QSeparator, QSpace, QSplitter, QTab, QTable, QTabs, QToolbar, QTree } from 'quasar'
import 'quasar/dist/quasar.css'
import '@quasar/extras/material-icons/material-icons.css'
import 'ol/ol.css'
import App from './SingleWindow.vue'
import './style.css'

createApp(App).use(Quasar, { plugins: { Notify, Dialog }, directives: { ClosePopup }, components: { QCheckbox, QDialog, QCardActions, QMarkupTable, QBadge, QBanner, QBreadcrumbs, QBreadcrumbsEl, QBtn, QCard, QCardSection, QChip, QExpansionItem, QFooter, QHeader, QIcon, QInput, QItem, QItemLabel, QItemSection, QLayout, QLinearProgress, QList, QPage, QPageContainer, QSelect, QSeparator, QSpace, QSplitter, QTab, QTable, QTabs, QToolbar, QTree } }).mount('#app')
