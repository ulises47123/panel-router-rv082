# Especificación HTTP — Sistema, Logs, Puertos y QoS (RV082 fw 2.0.0.19-tm)

Fuentes: copias locales en `exploracion/crudo/` + páginas bajadas con GET de lectura (solo páginas de formulario o vista) guardadas en `investigacion/crudo_sistema/` (los archivos `live_*.htm` son copias vivas de páginas que ya existían en local; coinciden byte a byte salvo contadores).
**No se hizo ningún POST ni ningún GET a URLs con restart/factory/firmware/backup/restore/.cgi, etc.**

---

## 0. Reglas generales (valen para todas las páginas)

| Tema | Detalle |
|---|---|
| Autenticación | HTTP **Basic** (`-u admin:admin`). El log del router lo confirma: `HTTP Basic authentication succeeded for user: admin`. No hay cookie ni sesión. "Logout" en el menú es solo `window.close()`. |
| Codificación | `charset=iso-8859-1`. Mandar `Content-Type: application/x-www-form-urlencoded` (salvo import de config, que es multipart). |
| Patrón | Cada página hace POST **a sí misma** (`action="<pagina>.htm"`). El servidor distingue la acción por los hidden `page`, `submitStatus`, `submitType`, `typeSubmit`. |
| Lectura de valores | El servidor ya escribe los valores en el HTML (`value='...'`, `checked`, `selected`). En esta versión las plantillas `#nk_get ...` llegan ya resueltas, salvo dentro de comentarios `<!-- -->`. |
| Lo que manda el navegador | Todos los `<input type=hidden>` y `text`; los `checkbox`/`radio` **solo si están marcados** (sin atributo `value` mandan `on`); los `<select>` con la opción seleccionada; **los campos `disabled` NO se mandan**; los `type=button` NO se mandan; un `type=submit` solo se manda si fue el botón usado. Los campos dentro de `<!-- -->` no existen. |
| Orden | El navegador manda los campos en orden de aparición en el DOM. Los ejemplos de abajo respetan ese orden. Conviene usar una lista de tuplas, no un diccionario. |
| Formulario `formdualwan` | Aparece arriba en todas las páginas (`dualwanEnabled=0`). Es otro formulario, **no** forma parte de ningún POST de guardado. Valor `0` significa que el router está en modo WAN + DMZ (una sola WAN). |
| Respuesta del POST | No verificada (no se hizo ningún POST). Lo esperable en esta familia es que devuelva la misma página ya con los valores nuevos. Hay que releer con GET y comparar. |

Esqueleto recomendado (Python, **NO ejecutado**):
```python
import requests, re, hashlib
R = "http://192.168.1.1/"
s = requests.Session(); s.auth = ("admin", "admin")
html = s.get(R + "password.htm", timeout=15).content.decode("latin-1")
# ... parsear, construir lista de tuplas en orden DOM ...
# s.post(R + "password.htm", data=[("page","password.htm"), ...], timeout=30)
```

---

## 1. password.htm — usuario y clave del admin

### 1.1 Lectura
- Usuario actual: texto en negrita `User Name: <b>admin</b>` (no es un input).
- Las claves no se pueden leer.
- `<input type=HIDDEN name="auth_key" value="1964300002">`. Es el mismo valor en la copia de exploración y en dos GET seguidos de hoy, así que **no parece un nonce por petición**. Puede ser fijo o cambiar por arranque, no se sabe. **Leerlo siempre con un GET justo antes del POST.**
- El campo `adminLoginTimeout` (`#nk_get LoginTimeout`) está **comentado**, así que no existe.

### 1.2 Guardado: "Save Settings" → `chSubmit(document.formPassword)` → `SendPassword()`
Validaciones de `chSubmit(F)`:
1. `oPass` no vacío, `nPass` no vacío y `cPass == nPass`. **No se puede cambiar solo el usuario**: hay que mandar siempre una clave nueva (puede ser igual a la vieja).
2. `nUser` y `cUser` no pueden tener espacios. Si alguno no está vacío, tienen que ser iguales.
3. Largo máximo 64 caracteres (onkeyup). `maxlength=65`.

`SendPassword()`:
```js
md5_pass = hex_md5(oPass + auth_key);   // MD5 hex en minúsculas (Paul Johnston, chrsz=8)
oPass    = "";                          // se manda VACÍO
document.formPassword.submit();         // POST password.htm
```
- **Solo la clave vieja va hasheada** (`MD5(clave_vieja + auth_key)`, concatenadas como texto). **La clave nueva y el usuario nuevo viajan en texto plano** (`nPass`, `cPass`, `nUser`, `cUser`).
- `chrsz=8`: cada carácter se trunca a 8 bits (`charCodeAt & 0xFF`). Con caracteres no ASCII el hash no coincide con un MD5 en UTF-8. **Usar solo ASCII**, o codificar en latin-1.

### 1.3 POST exacto
`POST /password.htm`, campos en este orden:
```
page=password.htm
oPass=                      (vacío)
md5_pass=<md5hex(oldpass + auth_key)>
auth_key=<valor leído>
nUser=<usuario nuevo o vacío>
cUser=<igual a nUser>
nPass=<clave nueva>
cPass=<igual a nPass>
```
Ejemplo (clave vieja `admin`, auth_key `1964300002`, usuario sin cambio, clave nueva `Nueva123`):
`md5("admin1964300002") = 06fc156ffc9b48c01c389695aab118b6`
```
page=password.htm&oPass=&md5_pass=06fc156ffc9b48c01c389695aab118b6&auth_key=1964300002&nUser=&cUser=&nPass=Nueva123&cPass=Nueva123
```

### 1.4 Riesgos
- Si sale bien, las credenciales Basic cambian **al instante**: la siguiente petición con admin:admin da 401. El programa tiene que pasar a usar las credenciales nuevas enseguida.
- Si la clave nueva se pierde, solo queda el reset físico de fábrica. Probar primero poniendo una clave nueva igual a la vieja.
- Qué pasa con `nUser` vacío (si conserva "admin") no está verificado. Lo esperable es que lo conserve.
- No hay HTTPS en esta URL: la clave nueva viaja en claro por la LAN.

---

## 2. time.htm / time1.htm / time2.htm — hora

`time.htm` solo hace `onLoad="document.location.href='time1.htm'"`, así que **la página real es `time1.htm` (NTP) o `time2.htm` (manual)**. Las dos llevan `page=time.htm`.

### 2.1 Lectura (time1.htm)
Hidden: `page=time.htm`, `submitStatus=1`, `statussetMode=1`, `pointbufList=0`.
- `<select name="time_zone">`: la opción con `selected` es la actual. Hoy es **`4` = (GMT-08:00) Pacific**, el valor de fábrica. Hay un segundo `<select name="time_zone">` con otra numeración, **dentro de un comentario: ignorarlo**.
- `enableDaylight` (checkbox, value=1, hoy sin marcar), `fromMonth=3`, `fromDay=28`, `toMonth=10`, `toDay=28`.
- `sNTP` (texto, maxlength 100), **hoy vacío**.
- `statussetMode` vale `1` en las dos páginas. Parece ser el modo guardado (1 = NTP). La hora actual se lee en time2.htm o en sys_log.htm (`Current Time:`).

Valores de `time_zone` (lista visible):
```
0 GMT-12 Intl Date Line W | 1 GMT-11 Midway/Samoa | 2 GMT-10 Hawaii | 3 GMT-9 Alaska | 4 GMT-8 Pacific
5 GMT-7 Arizona | 6 GMT-7 Chihuahua | 7 GMT-7 Mountain | 8 GMT-6 C.America | 9 GMT-6 Central
10 GMT-6 Mexico City | 11 GMT-6 Saskatchewan | 12 GMT-5 Bogota/Lima/Quito | 13 GMT-5 Eastern
14 GMT-5 Indiana | 15 GMT-4 Atlantic | 16 GMT-4 Caracas/La Paz | 17 GMT-4 Santiago | 18 GMT-3:30 Newfoundland
19 GMT-3 Brasilia | 20 GMT-3 Buenos Aires, Georgetown | 21 GMT-3 Greenland | 22 GMT-2 Mid-Atlantic
23 GMT-1 Azores | 24 GMT-1 Cape Verde | 25 GMT Casablanca | 26 GMT London | 27..31 GMT+1 | 32..37 GMT+2
38..41 GMT+3 | 42 GMT+3:30 | 43,44 GMT+4 | 45 GMT+4:30 | 46,47 GMT+5 | 48 GMT+5:30 | 49 GMT+5:45
50..52 GMT+6 | 53 GMT+6:30 | 54,55 GMT+7 | 56..60 GMT+8 | 61..63 GMT+9 | 64,65 GMT+9:30 | 66..70 GMT+10
71 GMT+11 | 72,73 GMT+12 | 74 GMT+13
```
(La lista completa con nombres está en `crudo_sistema/time1.htm`, líneas 640-714.)

### 2.2 Guardar NTP: `chSubmit(document.formTime)` en time1.htm
No hay validaciones, solo `F.submit()`. Al cargar la página, `chDaylight()` **deshabilita** fromMonth/fromDay/toMonth/toDay si `enableDaylight` no está marcado. En ese caso **no se mandan**.

`POST /time1.htm`:
```
page=time.htm&submitStatus=1&statussetMode=1&pointbufList=0&setMode=1&time_zone=20&sNTP=pool.ntp.org
```
Con horario de verano:
```
page=time.htm&submitStatus=1&statussetMode=1&pointbufList=0&setMode=1&time_zone=20&enableDaylight=1&fromMonth=3&fromDay=28&toMonth=10&toDay=28&sNTP=pool.ntp.org
```
Validaciones onBlur (`time24Check`): mes 1-12, día 1-31 según el mes (31 no vale en meses de 30 días, febrero ≤ 29).

Clic en la radio NTP dentro de time1 → `falseSubmit`: el mismo POST con `submitStatus=0`, que solo recarga la vista sin guardar.

### 2.3 Guardar hora manual: `chMTime(document.formTime)` en time2.htm
Valida que no haya vacíos y los rangos: hora 0-23, minuto y segundo 0-59, mes 1-12, día según mes, año 0-9999. Este formulario **no lleva `time_zone`**.

`POST /time2.htm`:
```
page=time.htm&submitStatus=1&statussetMode=1&pointbufList=0&setMode=2&settime_hours=14&settime_minutes=5&settime_seconds=0&settime_month=11&settime_day=12&settime_year=2026
```
Para volver de manual a NTP hay que hacer el POST de 2.2 con `setMode=1`. En el navegador, la radio NTP de time2 solo navega por GET a time1.htm.

### 2.4 Riesgos
Bajo. Con `sNTP` vacío no se sabe qué servidor usa. El año va con 4 dígitos.

---

## 3. sys_diag.htm — Ping y DNS Lookup

### 3.1 Estructura
El servidor arma la página según el modo actual (`diagType`). Hoy está `diagType=2` (Ping) marcado y **el bloque DNS viene comentado por el servidor**. Si se pasa a DNS pasa lo contrario (lo maneja `chDismatch()`: si existe `shNSLookup`, marca DNS). Las opciones 3 (Find Network Path) y 4 (Packet Trace) están comentadas ("Not support yet").

Campos activos en modo Ping, en orden DOM: `page=sys_diag.htm`, `submitStatus=1`, `diagType` (radio 1|2), `shPing` (hidden vacío), `pingAddr` (texto, max 64), `submitType=2`.
En modo DNS: `page`, `submitStatus`, `diagType`, `shNSLookup` (hidden vacío), `dnsName` (max 64), `submitType=1`.

### 3.2 Lanzar
- **Cambiar de modo** (clic en radio → `falseSubmit`): `submitStatus=0`.
  `page=sys_diag.htm&submitStatus=0&diagType=1&shPing=&pingAddr=&submitType=2` (de Ping a DNS).
- **Ping** (botón Go → `typeSubmit('2',F)`: pone `submitType=2` y hace submit):
  `POST /sys_diag.htm`
  `page=sys_diag.htm&submitStatus=1&diagType=2&shPing=&pingAddr=8.8.8.8&submitType=2`
- **DNS** (estando ya en modo DNS → `typeSubmit('1',F)`):
  `page=sys_diag.htm&submitStatus=1&diagType=1&shNSLookup=&dnsName=www.google.com&submitType=1`
  Mandarlo directo sin el paso de cambio de modo probablemente funcione, pero no está verificado.

### 3.3 Dónde se lee el resultado
**No hay otra página ni ventana emergente.** Según `help_sys_diag.htm`, el resultado aparece "at the bottom of the screen", es decir, **en el HTML que devuelve el mismo POST a sys_diag.htm**. El ping muestra paquetes transmitidos/recibidos/perdidos y RTT mín/máx/prom; el DNS muestra la IP o "Address Resolving Failed". En la plantilla vacía no hay marcador para el resultado (el `<span name="ping">` está en el bloque comentado), así que **el formato exacto no se conoce**. Para descubrirlo: hacer un ping real y comparar la respuesta con el GET. Lo más probable es que el bloque aparezca después de la tabla `Ping host or IP address`.
- El ping tarda unos segundos: usar timeout ≥ 20 s.
- Ping solo acepta IP según la ayuda. Para un nombre, resolverlo antes con DNS Lookup.

### 3.4 Riesgos
Bajo: no toca la configuración. Lo único persistente es el modo (`diagType`) que queda guardado para el siguiente GET.

---

## 4. log_setting.htm — configuración de logs

### 4.1 Lectura
Hidden: `page=log_setting.htm`, `submitStatus=1`, `hostName='TP-VPN'` (nombre del host; si está vacío y se activa e-mail, la página tira un alert).
- Syslog: `remoteLogger` (hidden 0/1, **recalculado** por `chLogServer()` al cargar), `enLogServer` (checkbox **sin value** → manda `on`; hoy sin marcar), `LogServerName='0.0.0.0'` (max 39). Queda **disabled** si `enLogServer` no está marcado.
- E-mail: `mailAlert` (hidden 0/1, recalculado por `chEmail()`), `enEmail` (checkbox, value=`checkbox`), `smtpServerName`, `logPrefs_logEmailAddr` (max 63), `LogQueueLength=50` (10-1000), `LogTimeThreshold=10` (10-10080 min). Todos quedan **disabled** si `enEmail` no está marcado.
- Alert Log (checkbox value=1): `synflood`, `spoofed`, `winnuke`, `badflag` (Ping of Death), `login_fail` ✔, `OutputBlock`.
- General Log: `system_errs` ✔, `conn_blocked` (Deny), `conn_accepted` (Allow), `conf_change` ✔, `login_success` ✔. (`GeneralLog4/5` están comentados.)

### 4.2 Guardado: `chSubmit(n, F)` → `F.submitStatus = n`
| n | Botón | Efecto |
|---|---|---|
| 1 | Save Settings | Guarda. Si syslog está activo, exige `LogServerName`. Si e-mail está activo, exige `smtpServerName` y un e-mail con `@`. |
| 2 | E-mail Log Now | Manda el log por mail (exige smtp y e-mail). |
| 3 | Clear Log Now | **Borra el log.** Manda el formulario entero con `submitStatus=3`. |

`POST /log_setting.htm`, estado actual (syslog y mail apagados):
```
page=log_setting.htm&submitStatus=1&hostName=TP-VPN&remoteLogger=0&mailAlert=0&login_fail=1&system_errs=1&conf_change=1&login_success=1
```
Con syslog a 192.168.1.50 y Deny Policies activado:
```
page=log_setting.htm&submitStatus=1&hostName=TP-VPN&remoteLogger=1&enLogServer=on&LogServerName=192.168.1.50&mailAlert=0&login_fail=1&system_errs=1&conn_blocked=1&conf_change=1&login_success=1
```
Con e-mail: después de `mailAlert=1` va `enEmail=checkbox&smtpServerName=...&logPrefs_logEmailAddr=a@b.com&LogQueueLength=50&LogTimeThreshold=10`.

### 4.3 Riesgos
- **Un checkbox que no se manda queda desactivado.** Mandar siempre todos los que se quieran encendidos.
- `submitStatus=3` borra el log sin pedir confirmación.
- Según la ayuda, el cambio de servidor syslog necesita reiniciar el router para aplicarse.

---

## 5. Lectura de logs: sys_log.htm, incoming_log.htm, outgoing_log.htm, log_report.htm

Se abren en ventanas emergentes con `openTable('sys_log.htm')` etc. **Un GET simple alcanza para leerlas** (verificado).

### 5.1 sys_log.htm (System Log), ~150 KB, 984 entradas
- Cabecera: `Current Time: &nbsp;&nbsp; Thu Nov 12 03:25:49 2026` (hora del router).
- Formulario `formLog` (`POST sys_log.htm`): `page=sys_log.htm`, `submitStatus=1`, `sys_log_cend='0'` (orden: 0 = ascendente, el más viejo primero), `LogType` (select), `LogClear=0`, botón submit `refresh`.
- Acciones (todas son POST, **no ejecutadas**):
  - Filtrar: `LogSel` → `submitStatus=2`, con `LogType` = 0 ALL, 1 System, 2 Access, 3 Firewall, 4 VPN. Probablemente el filtro queda guardado en el servidor.
  - Invertir orden: `chCend` → `submitStatus=11`.
  - Refresh: `submitStatus=1&...&refresh=+Refresh+`.
  - **Clear: `submitStatus=3` → borra el log.**
- Formato de cada entrada. Las filas **no tienen `</tr>`**, el mensaje puede traer saltos de línea y algunos tipos van envueltos en `<font color=16711680>`:
  ```
  <tr><td align=center>Nov 12 03:14:56 2026</td><td> &nbsp; &nbsp; Authentication Success </font></td><td> &nbsp; &nbsp;HTTP Basic authentication succeeded for user: admin</font></td>
  ```
  Regex: `<tr><td align=center>(.*?)</td><td>(.*?)</td><td>(.*?)</td>` (con DOTALL), después quitar etiquetas y `&nbsp;`, y hacer strip.
  Fecha: `"%b %d %H:%M:%S %Y"` con el día rellenado con espacio (`May  1 14:13:40 2017`).
  Tipos vistos: `System Log` (791), `Authentication Failure` (127), `Authentication Success` (64), `Connection Refused - Policy violation` (2). Ejemplos de mensaje: `--- System is up! ---`, `Firmware: v2.0.0.19-tm`, `192.168.1.250 access`, `2026/11/02 06:49:52 Bad login attempt for user: admin`, `IGMP 192.168.100.23->224.0.0.22 on ixp2`.

### 5.2 incoming_log.htm (~150 KB, 730 filas) y outgoing_log.htm
- Misma estructura de filas. Hidden: `page`, `submitStatus=1`, `in_log_cend`/`out_log_cend`. El orden se invierte con POST `submitStatus=11`.
- Incoming: todo `Connection Refused - Policy violation`, mensaje `TCP x.x.x.x:443->x.x.x.x:49238 on ixp1` (protocolo origen:puerto->destino:puerto on interfaz). `ixp0`=LAN (br0), `ixp1`=WAN, `ixp2`=DMZ/WAN2.
- Outgoing: hoy vacío (solo la cabecera de la tabla). Su Refresh es un GET (`window.location.replace('outgoing_log.htm')`).

### 5.3 log_report.htm (estadísticas por interfaz)
Solo lectura; "Refresh" es un link GET a log_report.htm. Tiene un `formlog_report` con hidden de contexto (`dualwanEnabled`, `dhcpEnabled=' checked'`, `lanDNS1/2`, `DmzRangeFlag`) pero **no tiene botón de guardar**. Tabla de 3 columnas (LAN=ixp0, WAN=ixp1, DMZ=ixp2), con estas filas:
Device Name, Status (`<font color=blue>Connected</font>` / `<font color=red>Down</font>`), IP Address, MAC Address (`xx-xx-xx-xx-xx-xx` / `-fd` / `-fe`), Subnet Mask, Default Gateway, DNS (a veces lo escribe JS con `document.write` a partir de los hidden), Received/Sent/Total Packets, Received/Sent/Total Bytes, Error Packets Received, Dropped Packets Received. Bytes/s y Sessions están comentados.
Parseo: celdas `<td width="22%" valign="middle">&nbsp; VALOR`, en orden de fila. La celda IP/DNS de la DMZ sale de un `<script>`: si el valor no aparece literal, calcularlo desde los hidden.

---

## 6. lan_setting.htm — Port Management (puertos 1-8, DMZ, WAN)

### 6.1 Lectura (por puerto n = 1..8)
| Campo | Tipo | Significado |
|---|---|---|
| `port{n}Disabled` | hidden | **No sirve para leer.** El servidor siempre escribe `'1'` aunque el puerto esté habilitado (`port1_information.htm` dice "Port Enabled"). `checkChecked()` lo **recalcula** al cargar: 1 si `portDisable{n}` está marcado, si no 0. |
| `portDisable{n}` | checkbox sin value | **Fuente real**: `checked` = deshabilitado. Hoy ninguno está marcado. |
| `port{n}Priority` | select | 1=High, 0=Normal (hoy Normal) |
| `port{n}Speed` | hidden | 0=10M, 1=100M (lo escribe `checkRadio`) |
| `speed{n}f` / `speed{n}s` | radios **con nombres distintos** y sin value | f=10M, s=100M. Uno lleva `checked`. |
| `port{n}Duplex` | hidden | 0=Half, 1=Full |
| `duplex{n}f` / `duplex{n}s` | radios | f=Half, s=Full |
| `auto{n}Neg` | hidden | 1/0, recalculado desde `autoNeg{n}` |
| `autoNeg{n}` | checkbox | Auto-negociación (hoy marcada en todos) |
| `port{n}VlanGroup` | select | 1..8 (hoy VLAN1) |

DMZ (puerto 9, "DMZ/Internet"): `DmzPortDisabled`/`portDisable9`, `DmzportSpeed`/`speed9f|s`, `DmzportDuplex`/`duplex9f|s`, `autoDmzNeg`/`autoNeg9`. No tiene prioridad ni VLAN.
WAN (puerto 10, "Internet"): `WanPortDisabled`/`portDisable10`, `WanportSpeed`/`speed10f|s`, `WanportDuplex`/`duplex10f|s`, `autoWanNeg`/`autoNeg10`.
Antes de los puertos van los hidden `page=lan_setting.htm` y `dualwanEnabled=0`.

Estado vivo por puerto, en solo lectura: `port{1..8}_information.htm`, `dmz_port_information.htm`, `wan_port_information.htm` (Link Status, Port Activity, Speed, Duplex, contadores). `lan_status.htm` hace lo mismo con un POST que solo elige el puerto a mostrar (`port=1..10`).

### 6.2 Guardado: `chSubmit()` → submit directo, sin validar
La lógica está en `checkChecked()`, que corre al cargar y en cada clic, y decide qué queda **disabled**:
- `autoNeg{n}` marcado → `auto{n}Neg=1` y los 4 radios de velocidad/dúplex quedan disabled (no se mandan).
- `portDisable{n}` marcado → `port{n}Disabled=1` y quedan disabled **Priority, los radios, autoNeg{n} y VlanGroup** (no se mandan).
- Validación única: no se pueden deshabilitar **los 8** puertos LAN a la vez (`aDisableAllPort`).

Bloque POST por puerto LAN, en orden DOM:
```
port{n}Disabled=<0|1>
[portDisable{n}=on]                 solo si está deshabilitado
[port{n}Priority=<1|0>]             solo si está habilitado
port{n}Speed=<0|1>
[speed{n}f=on | speed{n}s=on]       solo si está habilitado Y sin autoneg
port{n}Duplex=<0|1>
[duplex{n}f=on | duplex{n}s=on]     ídem
auto{n}Neg=<0|1>
[autoNeg{n}=on]                     solo si está habilitado y con autoneg
[port{n}VlanGroup=<1..8>]           solo si está habilitado
```
Ejemplo completo **del estado actual** (todo habilitado, autoneg, Normal, VLAN1), `POST /lan_setting.htm`:
```
page=lan_setting.htm&dualwanEnabled=0
&port1Disabled=0&port1Priority=0&port1Speed=1&port1Duplex=1&auto1Neg=1&autoNeg1=on&port1VlanGroup=1
&port2Disabled=0&port2Priority=0&port2Speed=1&port2Duplex=1&auto2Neg=1&autoNeg2=on&port2VlanGroup=1
... (igual para 3..8) ...
&DmzPortDisabled=0&DmzportSpeed=1&DmzportDuplex=1&autoDmzNeg=1&autoNeg9=on
&WanPortDisabled=0&WanportSpeed=1&WanportDuplex=1&autoWanNeg=1&autoNeg10=on
```
(Todo en una sola línea, sin saltos.)
- Deshabilitar el puerto 3: su bloque pasa a `port3Disabled=1&portDisable3=on&port3Speed=1&port3Duplex=1&auto3Neg=1`.
- Puerto 2 fijo en 10M/Half y prioridad High: `port2Disabled=0&port2Priority=1&port2Speed=0&speed2f=on&port2Duplex=0&duplex2f=on&auto2Neg=0&port2VlanGroup=1`.

### 6.3 Riesgos
- **Deshabilitar el puerto de la PC que maneja el router corta el acceso.** Si es el único puerto en uso, hay que ir al router y cambiar de puerto.
- **`portDisable10` apaga la WAN (se pierde Internet)** y `portDisable9` apaga la DMZ/WAN2.
- Forzar velocidad/dúplex distinto del equipo del otro lado → link caído o con errores.
- Cambiar VLAN aísla ese puerto del resto de la LAN.
- No confiar en el hidden `port{n}Disabled` del GET: siempre calcularlo.

---

## 7. qos.htm — Bandwidth Management

### 7.1 Lectura
Formulario `formQOS`, `POST qos.htm`. **No tiene hidden `page`.** Campos en orden DOM:
1. `dualwanEnabled=0`, `wanNumbers=2` (vale 2 aunque esté en modo DMZ), `submitStatus=1`.
2. `wan1Upstream='512'`, `wan2Upstream`, `wan3Upstream`, `wan4Upstream`, `wan1Downstream='512'`, `wan2Downstream`, `wan3Downstream`, `wan4Downstream`: hidden con los **valores guardados**. JS no los recalcula.
3. `ibwuWAN1='512'` (Upstream de WAN1, Kbit/s) e `ibwWAN1='512'` (Downstream), 1-100000 (`streamCheck`). `ibwuWAN2`/`ibwWAN2` solo existen con dualwan=1 (los escribe `document.write`).
4. `qosType` radio: `1` = Rate Control (hoy), `2` = Priority.
5. Modo Rate Control (el bloque Priority viene comentado por el servidor):
   - `service_menu1`: hidden **largo (~1100 caracteres) con HTML de `<option>`**. El navegador **lo devuelve tal cual** en el POST. Leerlo crudo del atributo `value='...'` (tiene `&` y `"` sin escapar).
   - `wanEnable` checkboxes value=1,2,…
   - `RC_protocol` select: se arma desde service_menu1 con la opción 0, después "Not Check Port" (16777235), después el resto.
   - `lanIP1=192`, `lanIP2=168`, `lanIP3=1` (hidden), `IPbegin`, `IPend` (último octeto), `Addr1..4=0` (hidden).
   - `RC_link` select: 2=Upstream, 1=Downstream.
   - `Percent` (Mín, Kbit/s), `Maxrate` (Máx), `RC_valid` (checkbox value=1).
   - `<select multiple name="qosRateList">`: **las reglas guardadas son sus `<option value=...>`**. Hoy está vacía, igual que `QosRate_table1.htm` (vista resumen en solo lectura).
6. Modo Priority: `service_menu2`, `P_protocol`, `P_link` (2/1), `Priority` (1=High, 2=Low), `P_valid`, `<select multiple name="qosPrioList">`.

IDs de servicio (de service_menu1): 16777216 All Traffic, 16777217 DNS, 16777218 FTP, 16777219 HTTP, 16777220 HTTP Secondary, 16777221 HTTPS, 16777222 HTTPS Secondary, 16777223 TFTP, 16777224 IMAP, 16777225 NNTP, 16777227 POP3, 16777228 SNMP, 16777229 SMTP, 16777230 TELNET, 16777231 TELNET Sec., 16777232 TELNETSSL, 16777233 DHCP, 16777234 L2TP, 16777235 Not Check Port, 16777236 ESP, 16777237 GRE. Los servicios propios se agregan desde `service01.htm`/`service02.htm` (otra ventana) y cambian la lista.

### 7.2 Formato de una regla
Rate Control (lo arma `RateaddSel`). El value es:
```
<svcID>{<lan1>.<lan2>.<lan3>.<ipIni>;<ipFin>(<a1>.<a2>.<a3>.<a4>)<dir>;<min>;<max>;<enable>;<wans>}
```
- `dir`: 2=Upstream, 1=Downstream. `min`/`max`: 1-99999 o 0 si quedó vacío (al menos uno es obligatorio, y min ≤ max). `enable`: 1/0. `wans`: números de WAN concatenados (`"1"`, `"12"`).
- `ipIni`/`ipFin`: 0-254; si vienen al revés se intercambian. `0;0` con All Traffic = todo el tráfico. `Addr` siempre es `0.0.0.0`.
- Ejemplo: HTTP para 192.168.1.10-20, subida, mín 0, máx 256, activa, WAN1:
  `16777219{192.168.1.10;20(0.0.0.0)2;0;256;1;1}`
  Texto que muestra el navegador (no se manda): `HTTP [TCP/80~80]->192.168.1.10~20(Upstream)=>0~256Kbit/sec->WAN1`
- Límite: 100 reglas Rate y 50 Priority. `ckDuplicate` rechaza duplicados.

Priority (`PrioaddSel`): `<svcID>{<dir>;<prio>;<enable>;<wans>}`, con prio 1=High, 2=Low. Ejemplo: `16777217{2;1;1;1}`.

### 7.3 Guardado: `chSubmit(document.formQOS)`
```js
submitStatus=1;
clearContent(F);          // RC_protocol = opción índice 12; IPbegin=IPend=Addr*=0; Percent=""; Maxrate="";
                          // RC_valid y TODOS los wanEnable desmarcados; RC_link no se toca
F.Percent.value="0";
ckSaveRate(...)           // con todos los wanEnable desmarcados vuelve 1 enseguida (no valida nada)
selAll(F.qosRateList);    // ¡INVIERTE el orden de la lista (exPosion) y selecciona todo!
submit();
```
POST de ejemplo (WAN1 1000/4000 Kbit/s y 2 reglas que en pantalla se ven como R1, R2). Una sola línea, `POST /qos.htm`:
```
dualwanEnabled=0&wanNumbers=2&submitStatus=1
&wan1Upstream=512&wan2Upstream=512&wan3Upstream=0&wan4Upstream=0
&wan1Downstream=512&wan2Downstream=512&wan3Downstream=0&wan4Downstream=0
&ibwuWAN1=1000&ibwWAN1=4000
&qosType=1
&service_menu1=<valor crudo urlencoded>
&RC_protocol=16777228            (la opción índice 12 de la lista armada; hoy SNMP)
&lanIP1=192&lanIP2=168&lanIP3=1&IPbegin=0&IPend=0&Addr1=0&Addr2=0&Addr3=0&Addr4=0
&RC_link=2&Percent=0&Maxrate=
&qosRateList=<R2 urlencoded>&qosRateList=<R1 urlencoded>      (en orden INVERSO al de pantalla)
```
Los campos `RC_protocol`, `IPbegin`, `Percent`, etc. van con "basura" porque así los deja el navegador. El servidor seguramente solo usa `qosRateList`, pero conviene replicarlos.

Cambiar entre Rate y Priority (`falseSubmit`): el mismo formulario con `submitStatus=0` y el `qosType` nuevo. **No está verificado si borra las reglas del otro tipo.**

### 7.4 Riesgos
- **Mandar `qosRateList` vacío o sin incluir todas las reglas las borra.** Siempre leer la lista, modificarla y mandarla completa.
- La inversión de orden de `selAll` puede ser intencional (si el servidor también invierte). Probar con 2 reglas y ver si el orden se mantiene después del GET.
- Upstream/Downstream mal puestos (por ejemplo 1 Kbit/s) estrangulan la WAN.
- `RC_protocol=índice 12` depende de la lista de servicios: calcularlo, no fijarlo a mano.
- El formato de las reglas que escribe el servidor en `<option>` no se pudo ver (la lista está vacía). Suponemos que es el mismo que arma el JS.

---

## 8. Mantenimiento: reinicio, respaldo, restauración, fábrica, firmware

Menú System Management (submenú de sys_diag/sys_dualwan3/qos): Dual WAN (`sys_dualwan3.htm` o `sys_dualwanw.htm` si dualwan=1), Bandwidth Management (`qos.htm`), SNMP (`sys_snmp.htm`), Diagnostic (`sys_diag.htm`), Factory Default (`sys_factory.htm`), Firmware Upgrade (`sys_firmware.htm`) y **"More... >>" → `sys_restart.htm`**. La segunda página del submenú (vista en sys_setting.htm) tiene **Restart (`sys_restart.htm`)** y **Setting Backup (`sys_setting.htm`)**. Lo mismo sale de `map.htm`.

### 8.1 Respaldo y restauración — `sys_setting.htm` (descargada con GET, verificada)
**Export (respaldo, descarga).** "Export" es un `<input type=submit name="Submit2" value="Export">` dentro de:
```html
<form name="formsys_setting2" method="post" action="RV082.exp">
  <input type=hidden name="page" value="sys_setting2.htm">
  <input type=hidden name="typeSubmit" value="2">
```
POST exacto (NO ejecutado):
```
POST /RV082.exp
Content-Type: application/x-www-form-urlencoded

page=sys_setting2.htm&typeSubmit=2&Submit2=Export
```
La respuesta es el archivo de configuración binario (por defecto "RV082.exp" según la ayuda) y "puede tardar hasta un minuto". Guardar `response.content` tal cual, en binario. No pide confirmación. Lo esperable es que no cambie nada en el router.

**Import (restauración):**
```html
<form name="formsys_setting1" method="post" action="sys_setting.htm" enctype="multipart/form-data">
  <input type=hidden name="page" value="sys_setting1.htm">
  <input type=hidden name="typeSubmit" value="1">
  <input type="FILE" name="importFile">
  <input type="button" value="Import" onClick="chImport(this.form);">   <!-- no se manda -->
```
`chImport`: exige un archivo y pide `confirm("Are you sure you want to import configuration file right now?")`, después hace submit.
POST (NO ejecutado): `multipart/form-data` a `/sys_setting.htm` con las partes `page=sys_setting1.htm`, `typeSubmit=1` y `importFile` (filename=RV082.exp, application/octet-stream).
**Riesgo MUY alto**: un archivo malo o de otra versión puede dejar el router inaccesible. Según la ayuda hay que **reiniciar después** para aplicar.

### 8.2 Reinicio — `sys_restart.htm` (NO descargada por la regla de "restart")
Lo seguro: es la página destino de "More... >>"; en lg.js están `cRestart = "Are you sure you want to restart router?"` y `wRestart = "Restart router..."`.
Lo inferido por el patrón de las demás páginas, **sin verificar**: un formulario `method=post action="sys_restart.htm"` con hidden `page=sys_restart.htm` (y probablemente `submitStatus`/`typeSubmit`), y un botón "Restart Router" que hace `if (confirm(cRestart)) { window.status=wRestart; F.submit(); }`. O sea: el reinicio sería un **POST a sys_restart.htm**; un GET solo debería mostrar la página.
**Para tener los nombres exactos falta un GET de `sys_restart.htm`**, que según la regla tiene que autorizar el usuario. La misma página también sirve para la segunda parte del submenú.

### 8.3 Factory Default — `sys_factory.htm` (no descargada)
lg.js: `cFactoryDefault = "Are you sure you want to return to default setting?"`, `wDefaultSetting = "Return to default setting..."`. Lo inferido es un POST a sys_factory.htm con confirmación. **Borra toda la configuración y la clave** (vuelve a admin/admin y LAN 192.168.1.1). No automatizar.

### 8.4 Firmware Upgrade — `sys_firmware.htm` (no descargada)
lg.js: `aSelectFile = "Please select a file first!"`, `cFirmware = "Are you sure you want to upgrade firmware right now?"`, `wUpgradeFirmware`, y la página de error `BadFile.htm` ("Bad upgrade file !"). Lo inferido es un formulario multipart con un `<input type=file>`, POST a sys_firmware.htm o a un .cgi. **Riesgo de dejar el equipo inservible.** No automatizar.

---

## 9. Comportamientos raros detectados
1. `port{n}Disabled` llega siempre en `'1'` aunque el puerto esté habilitado. Hay que usar el `checked` del checkbox.
2. qos.htm **invierte el orden de las reglas** antes de mandarlas y devuelve el hidden enorme `service_menu1`.
3. qos.htm manda valores "basura" fijos (`RC_protocol` = índice 12, `Percent=0`, `IPbegin=0`).
4. En password.htm la clave vieja va con MD5(clave+auth_key), pero **la nueva va en claro**. `auth_key` no cambió entre peticiones.
5. time.htm es solo una redirección; el formulario real está en time1.htm o time2.htm y lleva `page=time.htm`. El huso actual es 4 (Pacífico, el de fábrica) y el NTP está vacío.
6. El resultado de Ping/DNS no tiene un contenedor en la plantilla: viene en la respuesta del POST.
7. Seguridad: sys_log tiene **127 "Authentication Failure"**. Hay un barrido de usuarios (admin, root, cisco, Administrator…) en mayo de 2017, justo después de una entrada `10.x.x.x access`; los fallos no muestran la IP, así que el origen es una suposición y un intento fallido de admin el 02/11/2026.
