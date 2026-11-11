<script setup lang="ts">
import { useRoute } from 'vue-router'
import StarField from '@/components/StarField.vue'

const route = useRoute()
</script>

<template>
  <!-- Slow star drift only on the auth/public pages: fewer glass layers to re-blur there. -->
  <StarField :drift="route.meta.public === true" />
  <RouterView />
</template>
