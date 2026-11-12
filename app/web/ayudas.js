// Textos de los botones "?" de cada sección.
window.AYUDAS = {
inicio: `<h3>Inicio</h3>
<p>Resumen del router: si tiene internet, su IP pública (WAN), la IP de la red interna (LAN),
cuánto tiempo lleva encendido y qué puertos tienen un cable conectado.</p>
<ul><li><b>WAN</b> = el puerto "Internet" del router, donde va el cable del proveedor.</li>
<li><b>LAN</b> = los puertos 1 a 8, donde van las computadoras de la oficina.</li>
<li>Si la IP WAN dice <code>0.0.0.0</code>, el router no está recibiendo internet.</li></ul>`,

internet: `<h3>Internet (WAN)</h3>
<p>Cómo se conecta el router al proveedor de internet. Elegí la opción que te indique tu proveedor:</p>
<ul><li><b>Automática (DHCP)</b>: lo más común cuando el router va conectado a otro módem. No hay que completar nada.</li>
<li><b>IP fija</b>: el proveedor te dio una IP, máscara, puerta de enlace y DNS.</li>
<li><b>PPPoE</b>: el proveedor te dio usuario y contraseña (típico de fibra o ADSL en modo bridge).</li></ul>
<p><b>DNS</b>: si no sabés, podés usar <code>8.8.8.8</code> y <code>1.1.1.1</code>.</p>
<p><b>MTU</b>: dejalo en automático salvo que el proveedor indique otro valor (PPPoE suele usar 1492).</p>`,

lan: `<h3>Red local (LAN)</h3>
<p>Es la dirección del router dentro de la oficina. Las computadoras lo usan como "puerta de enlace".</p>
<div class="aviso amarillo">Si cambiás la IP del router, este programa y todas las computadoras pierden la conexión
hasta que obtengan una IP nueva (o se reinicien). Anotá la IP nueva antes de guardar.</div>
<p>El <b>nombre del equipo</b> y el <b>dominio</b> solo los piden algunos proveedores; se pueden dejar como están.</p>`,

dhcp: `<h3>DHCP y equipos</h3>
<p>El servidor DHCP reparte IPs automáticas a las computadoras, celulares e impresoras.</p>
<ul><li><b>Rango</b>: desde qué IP hasta qué IP reparte (ej. 192.168.1.100 a 192.168.1.149 = 50 equipos).</li>
<li><b>Tiempo de préstamo</b>: cada cuántos minutos el equipo renueva su IP (1440 = 1 día).</li>
<li><b>IP fija por equipo (reserva)</b>: hace que un equipo (por su MAC) reciba siempre la misma IP.
Útil para impresoras, cámaras o servidores. Usá una IP <i>fuera</i> del rango automático.</li>
<li><b>Equipos conectados</b>: lista de quién recibió IP del router.</li></ul>
<p>La MAC se ve en Windows con <code>ipconfig /all</code> ("Dirección física").</p>`,

reenvio: `<h3>Reenvío de puertos</h3>
<p>Permite que desde internet se llegue a un equipo de la oficina (por ejemplo una cámara, un servidor web o un sistema de facturación).</p>
<ol><li>Elegí el servicio (o creá uno con su protocolo y puertos).</li>
<li>Escribí la IP del equipo de destino (conviene que tenga IP fija por reserva DHCP).</li>
<li>Guardá.</li></ol>
<div class="aviso amarillo">Cada puerto abierto es una puerta a internet: abrí solo lo necesario.
Si el router está detrás de otro módem, también hay que abrir el puerto en ese módem.</div>
<p><b>UPnP</b>: deja que los programas abran puertos solos. Cómodo pero menos seguro; en empresas suele dejarse apagado.</p>`,

dmz: `<h3>Equipo expuesto (DMZ)</h3>
<p>Manda <b>todo</b> el tráfico entrante de internet a un único equipo. Solo se usa para pruebas o equipos especiales.</p>
<div class="aviso rojo">Ese equipo queda totalmente expuesto. Si solo necesitás uno o dos puertos, usá "Reenvío de puertos".</div>`,

seguridad: `<h3>Seguridad (firewall)</h3>
<ul><li><b>Firewall</b>: protección general. Debe estar encendido.</li>
<li><b>SPI</b>: revisa que el tráfico que entra corresponda a algo que se pidió desde adentro.</li>
<li><b>Protección DoS</b>: frena ataques que intentan saturar el router.</li>
<li><b>Bloquear pedidos desde internet</b>: el router no responde pings ni escaneos desde afuera.</li>
<li><b>Administración remota</b>: permite entrar a la configuración desde internet. Mantener <b>apagada</b> salvo necesidad (y con clave fuerte).</li>
<li><b>Bloqueos web</b>: Java, ActiveX, cookies y proxys en páginas web (pueden romper sitios; usar con cuidado).</li></ul>`,

reglas: `<h3>Reglas de acceso</h3>
<p>Permiten <b>permitir o bloquear</b> tráfico según el equipo, el servicio y el horario.
Ejemplos: bloquear internet a una PC fuera del horario laboral, o impedir que la red use cierto puerto.</p>
<ul><li>Las reglas se evalúan por <b>prioridad</b> (la de número más bajo primero).</li>
<li>El router ya trae reglas por defecto (permitir todo lo que sale de la LAN, bloquear lo que entra desde internet).</li></ul>
<div class="aviso rojo">Una regla "Bloquear todo desde la LAN" puede dejarte sin acceso al propio router.
Probá primero con un solo equipo.</div>`,

filtro: `<h3>Bloqueo de sitios web</h3>
<p>Bloquea páginas por <b>dominio</b> (ej. <code>facebook.com</code>) o por <b>palabra clave</b> en la dirección (ej. <code>juegos</code>).</p>
<ul><li>Podés elegir un <b>horario</b> en que el bloqueo está activo (ej. lunes a viernes de 8 a 17).</li>
<li>Funciona con sitios <code>http</code>; con <code>https</code> el router solo ve el dominio, así que conviene bloquear por dominio.</li></ul>`,

ancho: `<h3>Control de ancho de banda</h3>
<p>Reparte la velocidad de internet para que un solo equipo (o una descarga) no deje sin internet al resto.</p>
<ol><li><b>Medí tu conexión</b> en <code>fast.com</code> o <code>speedtest.net</code> y anotá subida y bajada.</li>
<li>Cargala en "Velocidad de tu conexión" en <b>kbit/s</b> (1 Mbit/s = 1000 kbit/s; 50 Mbit/s = 50000). Si queda baja, el router frena a todos.</li>
<li>Agregá reglas:
<ul><li><b>Máximo</b>: tope de velocidad (ej. PC de invitados: máximo 2000 kbit/s).</li>
<li><b>Mínimo garantizado</b>: reserva velocidad (ej. la PC de facturación: mínimo 1000 kbit/s).</li></ul></li></ol>
<ul><li><b>Bajada</b> = descargas, videos, navegar. <b>Subida</b> = enviar archivos, videollamadas, cámaras.</li>
<li>Ningún mínimo o máximo puede superar la velocidad de la conexión.</li>
<li>Conviene que el equipo tenga IP fija (reserva en "DHCP y equipos") para que la regla siempre le aplique.</li></ul>`,

puertos: `<h3>Puertos del switch</h3>
<p>Muestra los 8 puertos de red. Se puede <b>apagar</b> un puerto (por ejemplo uno que está en una sala pública)
o darle <b>prioridad alta</b> (por ejemplo al de un teléfono IP o un servidor).</p>
<div class="aviso amarillo">No apagues el puerto donde está conectada esta computadora: perderías la conexión con el router.</div>`,

herramientas: `<h3>Herramientas</h3>
<ul><li><b>Ping</b>: prueba si el router llega a una dirección (ej. <code>8.8.8.8</code> para probar internet, o la IP de una PC).</li>
<li><b>Buscar dominio (DNS)</b>: muestra qué IP corresponde a un nombre (ej. <code>google.com</code>). Si falla, el problema es de DNS.</li>
<li><b>Registro</b>: últimos eventos del router (conexiones, bloqueos, errores).</li></ul>`,

sistema: `<h3>Sistema</h3>
<ul><li><b>Contraseña</b>: el router viene con <code>admin/admin</code>. Cambiala por una segura y guardala en un lugar confiable.
Después de cambiarla, este programa te pedirá la nueva.</li>
<li><b>Fecha y hora</b>: necesaria para que funcionen los horarios de las reglas y el registro.</li>
<li><b>Respaldo</b>: descarga un archivo con toda la configuración (guardalo antes de hacer cambios grandes).</li>
<li><b>Reiniciar</b>: reinicia el router (corta internet ~1 minuto).</li></ul>`,

vpn: `<h3>Cómo poner la VPN (acceso desde afuera de la oficina)</h3>
<p>Con esto, una PC con Windows 10 que está en otro lugar (casa, viaje) entra a la red de la oficina
<b>como si estuviera enchufada al router</b>: ve las carpetas compartidas, impresoras, y sale a internet por la oficina.</p>
<p><b>Ventajas</b>: todo gratis y de código libre, <b>sin abrir puertos</b> en el módem, <b>sin comprar dominio</b>,
y la otra PC <b>no instala nada</b> (usa la VPN que ya trae Windows).</p>

<h4>Lo que se usa</h4>
<ul><li><b>SoftEther VPN Server</b> (gratis, libre, sin límite de usuarios): se instala en una PC de la oficina que quede siempre encendida y conectada por cable al router.</li>
<li><b>VPN Azure</b> (servicio gratuito de SoftEther): le da a tu servidor una dirección tipo <code>vpn123456.vpnazure.net</code> y hace de puente, por eso no hay que abrir puertos.</li>
<li><b>VPN de Windows 10</b> en la otra PC, tipo <b>SSTP</b>.</li></ul>

<h4>Parte 1 — En la PC de la oficina (lo hace este panel)</h4>
<p>Usá una PC conectada <b>por cable</b> al router que quede siempre encendida. En la sección <b>VPN</b> de este panel:</p>
<ol>
<li><b>Descargar</b>: el panel baja el instalador oficial de SoftEther y verifica su firma digital.</li>
<li><b>Abrir instalador</b> (está en inglés):
<ol type="a">
<li>Aviso de Windows → <b>Sí</b>.</li>
<li><i>Welcome to the SoftEther VPN Setup Wizard</i> → <b>Siguiente</b>.</li>
<li><i>Select Software Components to Install</i> → <b>SoftEther VPN Server</b> → <b>Siguiente</b>.</li>
<li><i>End User License Agreement</i> → marcar <i>I agree…</i> → <b>Siguiente</b>.</li>
<li><i>Important Notices</i> → <b>Siguiente</b>. <i>Directory to Install</i> → dejar como está → <b>Siguiente</b>.</li>
<li><i>Ready to Install</i> → <b>Siguiente</b> y esperar.</li>
<li><i>Setup Finished</i> → <b>desmarcar</b> <i>Start the SoftEther VPN Server Manager</i> → <b>Finalizar</b>.</li>
</ol>
Si se abre el <b>Server Manager</b> pidiendo contraseña: <b>no pongas nada y cerralo</b> (la crea el panel).</li>
<li><b>Configurar automáticamente</b>: el panel activa VPN Azure, la VPN de Windows (SSTP) y el puente con la placa conectada al router, y te muestra tu dirección <code>nombre.vpnazure.net</code>.</li>
<li><b>Crear usuarios</b>: uno por persona. Con <b>"Archivo para su PC"</b> descargás un archivo que crea la VPN en la otra PC con doble clic.</li>
<li>Dejá esa PC encendida (sin suspensión) y el router con internet.</li>
</ol>

<h4>Parte 2 — En la PC de afuera (Windows 10, sin instalar nada)</h4>
<ol>
<li><b>Inicio → Configuración → Red e Internet → VPN → Agregar una conexión VPN</b>.</li>
<li>Completá:
<ul><li>Proveedor de VPN: <b>Windows (integrado)</b></li>
<li>Nombre de la conexión: <code>Oficina</code></li>
<li>Nombre o dirección del servidor: <code>oficina-perez.vpnazure.net</code> (la de VPN Azure)</li>
<li>Tipo de VPN: <b>Protocolo de túnel de sockets seguros (SSTP)</b></li>
<li>Tipo de información de inicio de sesión: <b>Nombre de usuario y contraseña</b></li>
<li>Usuario: <code>juan</code> — Contraseña: la que creaste en el panel</li></ul></li>
<li>Guardar → clic en <b>Oficina → Conectar</b>.</li>
<li>Para comprobar: abrí <code>http://192.168.1.1</code> o ejecutá <code>ipconfig</code> (debe aparecer una IP 192.168.1.x).</li>
</ol>

<h4>Si algo falla</h4>
<ul><li><b>Error 0x80092013 / certificado</b>: revisá que escribiste exactamente la dirección <code>.vpnazure.net</code> (no <code>.softether.net</code>).</li>
<li><b>Error 691 / usuario o contraseña</b>: revisá que el usuario exista en la sección VPN del panel y cambiale la clave si hace falta.</li>
<li><b>Conecta pero no hay internet</b>: revisá el Local Bridge (debe ser el adaptador cableado al router) y que el router tenga internet.</li>
<li><b>Lento o se corta</b>: VPN Azure es un servicio académico gratuito sin garantía de velocidad.
Plan B: instalar el cliente SoftEther en la otra PC y conectar a <code>nombre.softether.net</code> (usa NAT-T, tampoco abre puertos).</li>
<li>La PC servidor <b>no puede comunicarse consigo misma</b> a través del bridge con los clientes VPN (limitación conocida); probá desde otra PC de la oficina.</li></ul>
<div class="aviso azul">Por qué no se usa la VPN propia del router (PPTP/IPsec): necesita IP pública y abrir puertos, y su cifrado de 2009 hoy es inseguro.</div>`
};
