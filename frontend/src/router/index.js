import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../stores/auth.js'

const Landing = () => import('../pages/Landing.vue')
const Servers = () => import('../pages/Servers.vue')
const AuthCallback = () => import('../pages/AuthCallback.vue')
const Admin = () => import('../pages/Admin.vue')
const DashboardLayout = () => import('../pages/DashboardLayout.vue')
const Overview = () => import('../pages/Overview.vue')
const Welcome = () => import('../pages/Welcome.vue')
const Leave = () => import('../pages/Leave.vue')
const AutoRole = () => import('../pages/AutoRole.vue')
const Logs = () => import('../pages/Logs.vue')
const Moderation = () => import('../pages/Moderation.vue')
const ReactionRoles = () => import('../pages/ReactionRoles.vue')
const Leveling = () => import('../pages/Leveling.vue')
const CustomCommands = () => import('../pages/CustomCommands.vue')
const SocialNotifications = () => import('../pages/SocialNotifications.vue')
const Stats = () => import('../pages/Stats.vue')
const TempVoice = () => import('../pages/TempVoice.vue')
const Starboard = () => import('../pages/Starboard.vue')
const Suggestions = () => import('../pages/Suggestions.vue')
const Birthday = () => import('../pages/Birthday.vue')
const ScheduledAnnouncements = () => import('../pages/ScheduledAnnouncements.vue')
const AntiRaid = () => import('../pages/AntiRaid.vue')
const Verification = () => import('../pages/Verification.vue')
const RoleMenus = () => import('../pages/RoleMenus.vue')
const Tickets = () => import('../pages/Tickets.vue')
const Giveaways = () => import('../pages/Giveaways.vue')
const Premium = () => import('../pages/Premium.vue')
const Impressum = () => import('../pages/legal/Impressum.vue')
const Privacy = () => import('../pages/legal/Privacy.vue')
const Terms = () => import('../pages/legal/Terms.vue')

const routes = [
  {
    path: '/',
    name: 'landing',
    component: Landing
  },
  {
    path: '/auth/callback',
    name: 'auth-callback',
    component: AuthCallback
  },
  {
    path: '/dashboard',
    name: 'servers',
    component: Servers,
    meta: { requiresAuth: true }
  },
  {
    path: '/admin',
    name: 'admin',
    component: Admin,
    meta: { requiresAuth: true, requiresOwner: true }
  },
  {
    path: '/dashboard/:guild_id',
    component: DashboardLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'overview', component: Overview },
      { path: 'welcome', name: 'welcome', component: Welcome },
      { path: 'leave', name: 'leave', component: Leave },
      { path: 'autorole', name: 'autorole', component: AutoRole },
      { path: 'logs', name: 'logs', component: Logs },
      { path: 'moderation', name: 'moderation', component: Moderation },
      { path: 'reaction-roles', name: 'reaction-roles', component: ReactionRoles },
      { path: 'leveling', name: 'leveling', component: Leveling },
      { path: 'custom-commands', name: 'custom-commands', component: CustomCommands },
      { path: 'social', name: 'social', component: SocialNotifications },
      { path: 'stats', name: 'stats', component: Stats },
      { path: 'tempvoice', name: 'tempvoice', component: TempVoice },
      { path: 'starboard', name: 'starboard', component: Starboard },
      { path: 'suggestions', name: 'suggestions', component: Suggestions },
      { path: 'birthday', name: 'birthday', component: Birthday },
      { path: 'scheduled', name: 'scheduled', component: ScheduledAnnouncements },
      { path: 'antiraid', name: 'antiraid', component: AntiRaid },
      { path: 'verification', name: 'verification', component: Verification },
      { path: 'rolemenus', name: 'rolemenus', component: RoleMenus },
      { path: 'tickets', name: 'tickets', component: Tickets },
      { path: 'giveaways', name: 'giveaways', component: Giveaways },
      { path: 'premium', name: 'premium', component: Premium }
    ]
  },
  {
    path: '/legal/impressum',
    name: 'legal-impressum',
    component: Impressum
  },
  {
    path: '/legal/datenschutz',
    name: 'legal-privacy',
    component: Privacy
  },
  {
    path: '/legal/privacy',
    redirect: '/legal/datenschutz'
  },
  {
    path: '/legal/agb',
    name: 'legal-terms',
    component: Terms
  },
  {
    path: '/legal/terms',
    redirect: '/legal/agb'
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0, behavior: 'smooth' }
  }
})

router.beforeEach(async (to, from, next) => {
  const auth = useAuth()

  // Wait for the initial /auth/me to resolve before deciding
  if (auth.state.status === 'unknown') {
    await auth.waitUntilResolved()
  }

  const isAuthed = auth.state.status === 'authenticated'

  if (to.meta.requiresAuth && !isAuthed) {
    return next({ path: '/', replace: true })
  }

  // Owner-only routes (admin panel): bounce non-owners back to the dashboard.
  if (to.meta.requiresOwner && !auth.state.user?.is_owner) {
    return next({ path: '/dashboard', replace: true })
  }

  next()
})

export default router
