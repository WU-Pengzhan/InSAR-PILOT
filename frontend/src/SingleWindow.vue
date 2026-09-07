<script setup lang="ts">
import {onMounted,onBeforeUnmount,ref,defineAsyncComponent} from 'vue'
import {setWindowOwner} from './window-session'
const App=defineAsyncComponent(()=>import('./App.vue'))
const state=ref('connecting')
const darkMode=localStorage.getItem('pilot-dark')==='true'
const zh=()=>localStorage.getItem('pilot-language')==='zh'
let socket:WebSocket|undefined,timer:ReturnType<typeof setTimeout>|undefined,disposed=false,generation=0,exiting=false
function clear(){generation++;clearTimeout(timer);setWindowOwner('');if(socket){socket.onclose=null;socket.onmessage=null;socket.close();socket=undefined}}
async function connect(){
  clear();if(disposed)return
  const current=generation
  if(state.value!=='occupied')state.value='connecting'
  try{
    const response=await fetch('/api/v1/session',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Pilot-Workbench':'1'},body:'{}',signal:AbortSignal.timeout(5000)})
    if(current!==generation || disposed)return
    if(!response.ok)throw Error('session')
    const ws=new WebSocket(`ws://${location.host}/api/v1/window`);socket=ws
    ws.onmessage=event=>{
      if(current!==generation || disposed)return
      const message=JSON.parse(event.data)
      if(message.state==='active'){setWindowOwner(message.owner);state.value='active'}
      else if(message.state==='ping')ws.send('pong')
      else if(message.state==='occupied'){state.value='occupied';setWindowOwner('')}
    }
    ws.onclose=()=>{if(current!==generation || disposed)return;if(exiting)return;setWindowOwner('');if(state.value!=='occupied')state.value='disconnected';timer=setTimeout(()=>void connect(),2500)}
    ws.onerror=()=>ws.close()
  }catch{if(current===generation && !disposed){state.value='disconnected';timer=setTimeout(()=>void connect(),2500)}}
}
function markExiting(){exiting=true}
function leave(){clear();state.value='disconnected'}
function lost(){leave();if(!disposed)timer=setTimeout(()=>void connect(),2500)}
onMounted(()=>{void connect();window.addEventListener('pilot-app-exiting',markExiting);window.addEventListener('pagehide',leave);window.addEventListener('pageshow',lost);window.addEventListener('pilot-window-lost',lost)})
onBeforeUnmount(()=>{disposed=true;clear();window.removeEventListener('pilot-app-exiting',markExiting);window.removeEventListener('pagehide',leave);window.removeEventListener('pageshow',lost);window.removeEventListener('pilot-window-lost',lost)})
</script>
<template>
  <App v-if="state==='active'"/>
  <main v-else class="window-gate" :class="{dark:darkMode}" data-testid="window-gate" role="status">
    <q-icon :name="state==='occupied'?'lock_clock':'desktop_windows'" size="44px"/>
    <h1>{{state==='occupied'?(zh()?'软件正在其他窗口使用':'Workbench in use in another window'):state==='connecting'?(zh()?'正在连接工作台…':'Connecting to the workbench…'):(zh()?'后台连接已断开':'Backend connection disconnected')}}</h1>
    <p>{{state==='occupied'?(zh()?'请关闭正在使用的窗口。释放后，此页面会自动连接，不会抢占现有窗口。':'Close the active window. This page will connect automatically when it is released, without taking over.'):(zh()?'确认后台正在运行。连接恢复后将自动进入。':'Ensure the backend is running. This page reconnects automatically.')}}</p>
    <p v-if="state==='occupied'">{{zh()?'异常断开后最多等待约 15 秒释放占用。后台任务继续运行。':'An unexpected disconnect may take about 15 seconds to release. Background tasks continue.'}}</p>
    <q-btn v-if="state!=='connecting'" outline no-caps :label="zh()?'重新检查':'Check again'" @click="connect"/>
  </main>
</template>
<style scoped>.window-gate{height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:32px;box-sizing:border-box;background:#f3f6f8;color:#243746}.window-gate h1{font-size:26px}.window-gate p{max-width:650px;line-height:1.8;font-size:14px}.window-gate.dark{background:#111d25;color:#e4edf2}</style>
