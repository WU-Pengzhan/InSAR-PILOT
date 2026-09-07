let owner=''
export function setWindowOwner(value:string){owner=value}
export function windowHeaders():Record<string,string>{return owner?{'X-Pilot-Window':owner}:{}}
export function windowUrl(url:string){return owner?`${url}${url.includes('?')?'&':'?'}window=${encodeURIComponent(owner)}`:url}
