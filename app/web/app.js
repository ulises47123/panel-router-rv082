// Panel del Router — interfaz en español para el Cisco/Linksys RV082
"use strict";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const C = () => $("#contenido");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const TITULOS = {
  inicio: "Inicio", internet: "Internet", lan: "Red local", dhcp: "DHCP y equipos", reenvio: "Abrir puertos",
  dmz: "Equipo expuesto (DMZ)", seguridad: "Seguridad", reglas: "Reglas de acceso", filtro: "Bloqueo de sitios", ancho: "Ancho de banda",
  puertos: "Puertos", herramientas: "Herramientas", sistema: "Sistema", vpn: "VPN (acceso remoto)",
};
const DIAS = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];
let seccion = "inicio";

// ---------------------------------------------------------------- utilidades
async function api(accion, datos) {
  const op = datos === undefined ? { method: "GET" } :
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(datos) };
  let r;
  try { r = await fetch("/api/" + accion, op); }
  catch (e) { throw new Error("El programa no responde. ¿Se cerró la ventana negra del servidor?"); }
  const j = await r.json().catch(() => ({ ok: false, error: "Respuesta inválida" }));
  if (!j.ok) throw new Error(j.error || "Error desconocido");
  return j.datos;
}
function toast(msg, tipo = "") {
  const d = document.createElement("div");
  d.className = tipo; d.textContent = msg;
  $("#toast").appendChild(d);
  setTimeout(() => d.remove(), tipo === "mal" ? 7000 : 3500);
}
function conectado(ok, txt) {
  $("#punto").className = "punto " + (ok ? "ok" : "mal");
  $("#estadoTxt").textContent = txt;
}
async function conBoton(btn, fn) {
  const t = btn.textContent;
  btn.disabled = true; btn.textContent = "Guardando…";
  try { await fn(); }
  catch (e) { toast(e.message, "mal"); }
  finally { btn.disabled = false; btn.textContent = t; }
}
const sw = (id, on, extra = "") => `<label class="sw"><input type="checkbox" id="${id}" ${on ? "checked" : ""} ${extra}><i></i></label>`;
const interruptor = (id, titulo, sub, on, extra = "") =>
  `<div class="interruptor"><div><b>${titulo}</b><small>${sub}</small></div>${sw(id, on, extra)}</div>`;
const campo = (id, etq, valor = "", ph = "", tipo = "text", sub = "") =>
  `<label class="campo">${etq}${sub ? ` <small>${sub}</small>` : ""}<input type="${tipo}" id="${id}" value="${esc(valor)}" placeholder="${esc(ph)}"></label>`;
const val = (id) => ($("#" + id)?.value ?? "").trim();
const chk = (id) => !!$("#" + id)?.checked;
const tarjeta = (titulo, desc, cuerpo) => `<div class="tarjeta"><h2>${titulo}</h2>${desc ? `<p class="desc">${desc}</p>` : ""}${cuerpo}</div>`;
function abrirModal(html) { $("#modalCuerpo").innerHTML = html; $("#modal").classList.add("ver"); }
function cerrarModal() { $("#modal").classList.remove("ver"); }
$("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") cerrarModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") cerrarModal(); });
function diasSelector(prefijo, marcados = []) {
  return `<div class="fila-inputs" style="gap:6px">${DIAS.map((d, i) =>
    `<label style="flex:0 0 auto;display:flex;gap:4px;align-items:center"><input type="checkbox" class="${prefijo}" value="${i}" ${marcados.includes(String(i)) || marcados.includes(i) ? "checked" : ""}>${d}</label>`).join("")}</div>`;
}

// ---------------------------------------------------------------- navegación
async function ir(s) {
  seccion = s;
  $$("#menu a").forEach((a) => a.classList.toggle("activo", a.dataset.s === s));
  $("#titulo").textContent = TITULOS[s];
  C().innerHTML = `<div class="cargando">Leyendo del router…</div>`;
  try { await VISTAS[s](); }
  catch (e) {
    C().innerHTML = `<div class="aviso rojo"><b>No se pudo leer el router.</b><br>${esc(e.message)}</div>`;
    if (/conectar|contraseña|incorrectos/i.test(e.message)) vistaConexion(e.message);
  }
}
$$("#menu a").forEach((a) => a.addEventListener("click", () => ir(a.dataset.s)));
$("#btnAyuda").addEventListener("click", () => abrirModal(AYUDAS[seccion] || "<p>Sin ayuda para esta sección.</p>"));
$("#btnRecargar").addEventListener("click", () => ir(seccion));
$("#btnSalir").addEventListener("click", async () => {
  if (!confirm("¿Cerrar el Panel del Router? Se cierra esta ventana y el programa.")) return;
  try { await api("salir", {}); } catch (e) { /* el servidor ya se está cerrando */ }
  document.body.innerHTML = `<div style="display:flex;height:100vh;align-items:center;justify-content:center;flex-direction:column;gap:12px;font-family:Segoe UI,sans-serif;color:#5d6779">
    <img src="logo.png" width="64" height="64" alt=""><b style="color:#1d2433;font-size:18px">Panel cerrado</b><span>Ya podés cerrar esta ventana.</span></div>`;
});

// ---------------------------------------------------------------- conexión
async function vistaConexion(msg) {
  const cfg = await api("config").catch(() => ({ ip: "192.168.1.1", usuario: "admin" }));
  conectado(false, "Sin conexión");
  C().insertAdjacentHTML("beforeend", tarjeta("Conexión con el router", "Datos para entrar al router (los mismos de su página web).",
    `<div class="campos">${campo("cIp", "IP del router", cfg.ip)}${campo("cUs", "Usuario", cfg.usuario)}${campo("cCl", "Contraseña", "", "••••", "password")}</div>
     <div class="botones"><button class="prim" id="cBtn">Conectar</button></div>
     <p class="desc" style="margin-top:12px">La PC debe estar conectada por cable a un puerto LAN (1 a 8) del router.</p>`));
  $("#cBtn").onclick = (e) => conBoton(e.target, async () => {
    await api("config", { ip: val("cIp"), usuario: val("cUs"), clave: $("#cCl").value });
    toast("Conectado", "ok"); ir("inicio");
  });
}

// ---------------------------------------------------------------- INICIO
async function vInicio() {
  const e = await api("estado");
  conectado(true, `Conectado a ${e.lan_ip}`);
  const led = (on, n, sub) => `<div class="puerto"><div class="led ${on ? "on" : ""}"></div><b>${n}</b><small>${sub}</small></div>`;
  C().innerHTML =
    (e.internet ? "" : `<div class="aviso amarillo"><b>El router no tiene internet.</b> La IP de internet es 0.0.0.0. Revisá que el cable del proveedor esté en el puerto <b>Internet</b> del router y la configuración en la sección Internet.</div>`) +
    tarjeta("Estado", "",
      `<div class="rejilla">
        <div class="dato"><span>Internet</span><b>${e.internet ? '<span class="etq ok">Conectado</span>' : '<span class="etq mal">Sin conexión</span>'}</b></div>
        <div class="dato"><span>IP de internet (WAN)</span><b>${esc(e.wan_ip)}</b></div>
        <div class="dato"><span>IP del router (LAN)</span><b>${esc(e.lan_ip)}</b></div>
        <div class="dato"><span>DNS</span><b>${esc(e.dns || "—")}</b></div>
        <div class="dato"><span>Encendido hace</span><b>${esc(e.encendido)}</b></div>
        <div class="dato"><span>Hora del router</span><b>${esc(e.hora_router)}</b></div>
        <div class="dato"><span>Equipo expuesto (DMZ)</span><b>${e.dmz_host ? '<span class="etq mal">Activo</span>' : '<span class="etq gris">No</span>'}</b></div>
        <div class="dato"><span>Firmware</span><b>${esc(e.firmware)}</b></div>
      </div>`) +
    tarjeta("Puertos", "Verde = hay un cable conectado y funcionando.",
      `<div class="puertos">${led(e.puertos.wan, "Internet", "WAN")}${led(e.puertos.dmz, "DMZ", "WAN2")}${e.puertos.lan.map((on, i) => led(on, i + 1, "LAN")).join("")}</div>`) +
    tarjeta("Equipo", "", `<div class="rejilla"><div class="dato"><span>Modelo</span><b>${esc(e.modelo)}</b></div><div class="dato"><span>N.º de serie</span><b>${esc(e.serie)}</b></div><div class="dato"><span>Fecha del firmware</span><b>${esc(e.firmware_fecha)}</b></div></div>`);
}

// ---------------------------------------------------------------- INTERNET
async function vInternet() {
  const w = await api("internet");
  C().innerHTML = tarjeta("Tipo de conexión", "Cómo se conecta el router a tu proveedor de internet.",
    `<div class="campos"><label class="campo">Tipo
      <select id="wTipo"><option value="dhcp">Automática (DHCP) — lo más común</option><option value="estatica">IP fija</option><option value="pppoe">PPPoE (usuario y contraseña)</option></select></label></div>
     <div id="wCampos" style="margin-top:14px"></div>
     <div class="interruptor" style="margin-top:8px"><div><b>MTU automático</b><small>Dejalo encendido salvo que el proveedor indique otro valor</small></div>${sw("wMtuA", w.mtu_auto)}</div>
     <div id="wMtuBox" class="campos">${campo("wMtu", "MTU", w.mtu, "1500", "number", "68 a 1500 (PPPoE suele usar 1492)")}</div>
     <div class="botones"><button class="prim" id="wGuardar">Guardar</button></div>`);
  $("#wTipo").value = w.tipo in { dhcp: 1, estatica: 1, pppoe: 1 } ? w.tipo : "dhcp";
  const pintar = () => {
    const t = $("#wTipo").value;
    let h = "";
    if (t === "dhcp") {
      h = interruptor("wDnsM", "Usar DNS propios", "Si está apagado usa los DNS del proveedor", w.dns_manual) +
        `<div class="campos" id="wDnsBox">${campo("wDns1", "DNS 1", w.dns1, "8.8.8.8")}${campo("wDns2", "DNS 2", w.dns2, "1.1.1.1")}</div>`;
    } else if (t === "estatica") {
      h = `<div class="campos">${campo("wIp", "IP de internet", w.ip, "ej. 200.45.10.20")}${campo("wMas", "Máscara", w.mascara || "255.255.255.0")}
        ${campo("wPue", "Puerta de enlace", w.puerta, "ej. 200.45.10.1")}${campo("wDns1", "DNS 1", w.dns1, "8.8.8.8")}${campo("wDns2", "DNS 2", w.dns2, "1.1.1.1")}</div>`;
    } else {
      h = `<div class="campos">${campo("wUs", "Usuario PPPoE", w.usuario || "", "el que te dio el proveedor")}
        ${campo("wCl", "Contraseña PPPoE", "", w.clave_guardada ? "(sin cambios)" : "", "password")}
        ${campo("wSrv", "Nombre de servicio", w.servicio || "", "normalmente vacío")}</div>
        ${interruptor("wMant", "Mantener siempre conectado", "Recomendado en una oficina", w.mantener !== false)}`;
    }
    $("#wCampos").innerHTML = h;
    const dm = $("#wDnsM");
    if (dm) { const f = () => $("#wDnsBox").style.display = dm.checked ? "" : "none"; dm.onchange = f; f(); }
  };
  pintar();
  $("#wTipo").onchange = pintar;
  const mtu = () => $("#wMtuBox").style.display = chk("wMtuA") ? "none" : "";
  $("#wMtuA").onchange = mtu; mtu();
  $("#wGuardar").onclick = (e) => {
    const t = $("#wTipo").value;
    if (t !== w.tipo && !confirm("Vas a cambiar el tipo de conexión a internet. Si los datos no son correctos el router quedará sin internet. ¿Continuar?")) return;
    conBoton(e.target, async () => {
      const d = { tipo: t, mtu_auto: chk("wMtuA"), mtu: val("wMtu"), dns1: val("wDns1"), dns2: val("wDns2") };
      if (t === "dhcp") d.dns_manual = chk("wDnsM");
      if (t === "estatica") Object.assign(d, { ip: val("wIp"), mascara: val("wMas"), puerta: val("wPue") });
      if (t === "pppoe") Object.assign(d, { usuario: val("wUs"), clave: $("#wCl").value, servicio: val("wSrv"), mantener: chk("wMant") });
      const r = await api("internet", d); toast(r.mensaje, "ok"); ir("internet");
    });
  };
}

// ---------------------------------------------------------------- RED LOCAL
async function vLan() {
  const l = await api("lan");
  C().innerHTML = tarjeta("Dirección del router", "La IP que usan las computadoras como puerta de enlace.",
    `<div class="aviso amarillo">Si cambiás la IP o la máscara, este programa y las computadoras se desconectan hasta obtener una IP nueva.</div>
     <div class="campos">${campo("lIp", "IP del router", l.ip)}
      <label class="campo">Máscara<select id="lMas">${Object.entries(l.mascaras).map(([k, v]) => `<option value="${k}" ${k === l.mascara ? "selected" : ""}>${v}</option>`).join("")}</select></label>
      ${campo("lNom", "Nombre del equipo", l.nombre, "", "text", "opcional")}${campo("lDom", "Dominio", l.dominio, "", "text", "opcional")}</div>
     <p class="desc" style="margin-top:12px">MAC del router (LAN): <code>${esc(l.mac)}</code></p>
     <div class="botones"><button class="prim" id="lGuardar">Guardar</button></div>`);
  $("#lGuardar").onclick = (e) => {
    if ((val("lIp") !== l.ip || $("#lMas").value !== l.mascara) &&
      !confirm(`Vas a cambiar la dirección del router a ${val("lIp")}. Se cortará la conexión. ¿Continuar?`)) return;
    conBoton(e.target, async () => {
      const r = await api("lan", { ip: val("lIp"), mascara: $("#lMas").value, nombre: val("lNom"), dominio: val("lDom") });
      toast(r.mensaje, "ok");
      if (!r.nueva_ip) ir("lan");
    });
  };
}

// ---------------------------------------------------------------- DHCP
async function vDhcp() {
  const [d, cl] = await Promise.all([api("dhcp"), api("clientes")]);
  let reservas = d.reservas.slice();
  const filasRes = () => reservas.length ? reservas.map((r, i) => `<tr><td>${esc(r.nombre || "—")}</td><td>${esc(r.ip)}</td><td><code>${esc(r.mac)}</code></td>
      <td>${r.activa ? '<span class="etq ok">Sí</span>' : '<span class="etq gris">No</span>'}</td><td><button class="chico" data-q="${i}">Quitar</button></td></tr>`).join("")
    : `<tr><td colspan="5" class="vacio">No hay reservas</td></tr>`;
  C().innerHTML =
    tarjeta("Servidor DHCP", "Reparte IPs automáticamente a los equipos de la red.",
      interruptor("dAct", "DHCP activado", "Si lo apagás, cada equipo necesita IP fija", d.activo) +
      `<div class="campos" style="margin-top:12px" id="dBox">
        <label class="campo">Desde<div class="fila-inputs"><span style="flex:0 0 auto;min-width:0;align-self:center">${esc(d.red)}.</span><input type="number" id="dDes" value="${esc(d.desde)}" min="1" max="254"></div></label>
        <label class="campo">Hasta<div class="fila-inputs"><span style="flex:0 0 auto;min-width:0;align-self:center">${esc(d.red)}.</span><input type="number" id="dHas" value="${esc(d.hasta)}" min="1" max="254"></div></label>
        ${campo("dMin", "Tiempo de préstamo (minutos)", d.minutos, "1440", "number", "1440 = 1 día")}
        ${campo("dDns1", "DNS 1 que se reparte", d.dns1, "vacío = el router")}${campo("dDns2", "DNS 2", d.dns2, "opcional")}</div>`) +
    tarjeta("IP fija por equipo (reservas)", "Un equipo (por su MAC) recibe siempre la misma IP. Ideal para impresoras, cámaras y servidores.",
      `<table><thead><tr><th>Nombre</th><th>IP</th><th>MAC</th><th>Activa</th><th></th></tr></thead><tbody id="dRes">${filasRes()}</tbody></table>
       <div class="fila-inputs" style="margin-top:12px">${campo("rNom", "Nombre", "", "impresora", "text", "máx. 12, sin espacios")}${campo("rIp", "IP", "", d.red + ".20")}${campo("rMac", "MAC", "", "aa-bb-cc-dd-ee-ff")}<button id="rAdd">Agregar</button></div>`) +
    `<div class="botones" style="margin:-4px 0 18px"><button class="prim" id="dGuardar">Guardar DHCP y reservas</button></div>` +
    tarjeta("Equipos conectados", `${cl.usadas} IPs repartidas · ${cl.libres} libres de ${cl.total}`,
      `<table><thead><tr><th>Nombre</th><th>IP</th><th>MAC</th><th>Préstamo</th><th></th></tr></thead><tbody>${cl.clientes.length ? cl.clientes.map((c) =>
        `<tr><td>${esc(c.nombre || "—")}</td><td>${esc(c.ip)}</td><td><code>${esc(c.mac)}</code></td><td>${esc(c.tiempo)}</td><td><button class="chico" data-fijar="${esc(c.ip)}|${esc(c.mac)}|${esc((c.nombre || "").replace(/\s/g, "").slice(0, 12))}">Fijar IP</button></td></tr>`).join("")
        : `<tr><td colspan="5" class="vacio">Ningún equipo pidió IP al router todavía</td></tr>`}</tbody></table>`);
  const pintarRes = () => {
    $("#dRes").innerHTML = filasRes();
    $$("[data-q]").forEach((b) => b.onclick = () => { reservas.splice(+b.dataset.q, 1); pintarRes(); toast("Quitada (falta Guardar)"); });
  };
  pintarRes();
  const box = () => $("#dBox").style.display = chk("dAct") ? "" : "none";
  $("#dAct").onchange = box; box();
  $("#rAdd").onclick = () => {
    if (!val("rIp") || !val("rMac")) return toast("Completá IP y MAC", "mal");
    reservas.push({ nombre: val("rNom"), ip: val("rIp"), mac: val("rMac"), activa: true });
    ["rNom", "rIp", "rMac"].forEach((i) => $("#" + i).value = "");
    pintarRes(); toast("Agregada (falta Guardar)");
  };
  $$("[data-fijar]").forEach((b) => b.onclick = () => {
    const [ip, mac, nom] = b.dataset.fijar.split("|");
    reservas.push({ nombre: nom, ip, mac, activa: true }); pintarRes(); toast("Agregada a reservas (falta Guardar)");
  });
  $("#dGuardar").onclick = (e) => {
    if (!chk("dAct") && d.activo && !confirm("¿Apagar el DHCP? Los equipos nuevos no recibirán IP.")) return;
    conBoton(e.target, async () => {
      const r = await api("dhcp", { activo: chk("dAct"), desde: val("dDes"), hasta: val("dHas"), minutos: val("dMin"), dns1: val("dDns1"), dns2: val("dDns2"), reservas });
      toast(r.mensaje, "ok"); ir("dhcp");
    });
  };
}

// ---------------------------------------------------------------- ABRIR PUERTOS
async function vReenvio() {
  const r = await api("reenvio");
  C().innerHTML =
    tarjeta("Puertos abiertos", "Desde internet se llega al equipo indicado. Máximo 30.",
      `<table><thead><tr><th>Servicio</th><th>Protocolo</th><th>Puerto</th><th>Equipo</th><th>Activo</th><th></th></tr></thead><tbody>${r.reenvios.length ? r.reenvios.map((x) =>
        `<tr><td>${esc(x.nombre)}</td><td>${esc(x.proto)}</td><td>${esc(x.puertos)}</td><td>${esc(x.ip)}</td><td>${sw("", x.activo, `data-act="${esc(x.valor)}"`)}</td><td><button class="chico" data-del="${esc(x.valor)}">Borrar</button></td></tr>`).join("")
        : `<tr><td colspan="6" class="vacio">No hay puertos abiertos</td></tr>`}</tbody></table>`) +
    tarjeta("Abrir un puerto", "Elegí un servicio conocido o escribí el puerto.",
      `<div class="campos">
        <label class="campo">Servicio<select id="pSrv"><option value="">Otro puerto (escribirlo)…</option>${r.servicios.map((s) => `<option value="${esc(s.id)}">${esc(s.texto)}</option>`).join("")}</select></label>
        ${campo("pIp", "IP del equipo de destino", "", r.red + ".50")}</div>
       <div class="campos" id="pOtro" style="margin-top:12px">${campo("pNom", "Nombre", "", "camaras", "text", "máx. 11, sin espacios")}
        <label class="campo">Protocolo<select id="pPro"><option value="TCP">TCP</option><option value="UDP">UDP</option><option value="AMBOS">TCP y UDP</option></select></label>
        ${campo("pDes", "Puerto (o desde)", "", "8000", "number")}${campo("pHas", "Hasta", "", "igual al anterior", "number", "opcional")}</div>
       <div class="botones"><button class="prim" id="pAdd">Abrir puerto</button></div>`) +
    tarjeta("UPnP", "", interruptor("pUpnp", "Permitir que los programas abran puertos solos (UPnP)", "Cómodo pero menos seguro; en empresas suele estar apagado", r.upnp));
  const otro = () => $("#pOtro").style.display = $("#pSrv").value ? "none" : "";
  $("#pSrv").onchange = otro; otro();
  $("#pAdd").onclick = (e) => conBoton(e.target, async () => {
    const x = await api("reenvio/agregar", { servicio_id: $("#pSrv").value, ip: val("pIp"), nombre: val("pNom"), proto: $("#pPro").value, desde: val("pDes"), hasta: val("pHas") });
    toast(x.mensaje, "ok"); ir("reenvio");
  });
  $$("[data-del]").forEach((b) => b.onclick = () => {
    if (!confirm("¿Borrar este puerto abierto?")) return;
    conBoton(b, async () => { const x = await api("reenvio/borrar", { valor: b.dataset.del }); toast(x.mensaje, "ok"); ir("reenvio"); });
  });
  $$("[data-act]").forEach((c) => c.onchange = async () => {
    try { const x = await api("reenvio/activar", { valor: c.dataset.act, activo: c.checked }); toast(x.mensaje, "ok"); ir("reenvio"); }
    catch (e) { toast(e.message, "mal"); c.checked = !c.checked; }
  });
  $("#pUpnp").onchange = async (e) => {
    try { const x = await api("upnp", { activo: e.target.checked }); toast(x.mensaje, "ok"); }
    catch (er) { toast(er.message, "mal"); e.target.checked = !e.target.checked; }
  };
}

// ---------------------------------------------------------------- DMZ
async function vDmz() {
  const d = await api("dmz");
  C().innerHTML = tarjeta("Equipo expuesto a internet", "Todo el tráfico de internet que no tenga un puerto abierto va a este equipo.",
    `<div class="aviso rojo">Ese equipo queda totalmente expuesto. Usalo solo si sabés lo que hacés; normalmente alcanza con "Abrir puertos".</div>
     ${interruptor("zAct", "Activar equipo expuesto", "", d.activo)}
     <div class="campos" id="zBox" style="margin-top:10px">${campo("zIp", "IP del equipo", d.ip, d.red + ".50")}</div>
     <div class="botones"><button class="prim" id="zGuardar">Guardar</button></div>`);
  const box = () => $("#zBox").style.display = chk("zAct") ? "" : "none";
  $("#zAct").onchange = box; box();
  $("#zGuardar").onclick = (e) => conBoton(e.target, async () => {
    const r = await api("dmz", { activo: chk("zAct"), ip: val("zIp") }); toast(r.mensaje, "ok"); ir("dmz");
  });
}

// ---------------------------------------------------------------- SEGURIDAD
async function vSeguridad() {
  const f = await api("firewall");
  C().innerHTML =
    (f.clave_de_fabrica ? `<div class="aviso rojo"><b>El router usa la contraseña de fábrica (admin).</b> Cualquiera en la red puede cambiar la configuración. Cambiala en <a href="#" id="irSis">Sistema</a>.</div>` : "") +
    (!f.firewall ? `<div class="aviso rojo">El firewall está apagado en el router.</div>` : "") +
    tarjeta("Protecciones", "Recomendado: todas encendidas.",
      interruptor("fSpi", "Inspección de conexiones (SPI)", "Solo deja entrar respuestas a lo que se pidió desde adentro", f.spi) +
      interruptor("fDos", "Protección contra ataques (DoS)", "Frena intentos de saturar el router", f.dos) +
      interruptor("fWan", "Bloquear pedidos desde internet", "El router no responde pings ni escaneos desde afuera", f.bloquear_wan) +
      interruptor("fMul", "Dejar pasar multicast", "Solo si usás IPTV u otro servicio que lo pida", f.multicast)) +
    tarjeta("Administración desde internet", "Permite entrar a la configuración del router desde afuera.",
      interruptor("fRem", "Administración remota", f.clave_de_fabrica ? "Bloqueado: primero cambiá la contraseña" : "Mantener apagada salvo necesidad", f.admin_remota, f.clave_de_fabrica ? "disabled" : "") +
      `<div class="campos" id="fRemBox" style="margin-top:10px">${campo("fPort", "Puerto", f.puerto_remoto || "8443", "8443", "number")}</div>`) +
    tarjeta("Bloqueos en páginas web", "Pueden hacer que algunos sitios no funcionen.",
      interruptor("fJava", "Bloquear Java", "", f.java) + interruptor("fCook", "Bloquear cookies", "", f.cookies) +
      interruptor("fAx", "Bloquear ActiveX", "", f.activex) + interruptor("fProx", "Bloquear proxys", "", f.proxy)) +
    `<div class="botones"><button class="prim" id="fGuardar">Guardar</button></div>`;
  $("#irSis")?.addEventListener("click", (e) => { e.preventDefault(); ir("sistema"); });
  const rb = () => $("#fRemBox").style.display = chk("fRem") ? "" : "none";
  $("#fRem").onchange = rb; rb();
  $("#fGuardar").onclick = (e) => conBoton(e.target, async () => {
    const r = await api("firewall", { spi: chk("fSpi"), dos: chk("fDos"), bloquear_wan: chk("fWan"), multicast: chk("fMul"),
      admin_remota: chk("fRem"), puerto_remoto: val("fPort"), java: chk("fJava"), cookies: chk("fCook"), activex: chk("fAx"), proxy: chk("fProx") });
    toast(r.mensaje, "ok"); ir("seguridad");
  });
}

// ---------------------------------------------------------------- REGLAS
async function vReglas() {
  const [r, servicios] = await Promise.all([api("reglas"), api("reglas/servicios")]);
  const origen = (o) => o.replace(/^([\d.]+) ~ \1$/, "$1").replace(" ~ ", " a ");
  C().innerHTML =
    tarjeta("Reglas actuales", "Se aplican de arriba hacia abajo. Las grises son las reglas de fábrica.",
      `<table><thead><tr><th>#</th><th>Activa</th><th>Acción</th><th>Servicio</th><th>Equipo(s)</th><th>Destino</th><th>Horario</th><th></th></tr></thead><tbody>${r.reglas.map((x) =>
        `<tr style="${x.fija ? "opacity:.6" : ""}"><td>${esc(x.prioridad)}</td><td>${x.fija ? (x.activa ? "Sí" : "No") : sw("", x.activa, `data-ract="${esc(x.num_estado || x.num)}"`)}</td>
        <td><span class="etq ${x.accion === "Bloquear" ? "mal" : "ok"}">${esc(x.accion)}</span></td><td>${esc(x.servicio.replace("All Traffic", "Todo"))}</td>
        <td>${esc(x.interfaz)} · ${esc(origen(x.origen))}</td><td>${esc(origen(x.destino))}</td><td>${esc(x.horario)}${x.dias ? "<br><small>" + esc(x.dias) + "</small>" : ""}</td>
        <td>${x.fija ? "" : `<button class="chico" data-rdel="${esc(x.num)}">Borrar</button>`}</td></tr>`).join("")}</tbody></table>`) +
    tarjeta("Nueva regla", "Ejemplo: bloquear internet a la PC 192.168.1.60 de lunes a viernes de 8 a 17.",
      `<div class="campos">
        <label class="campo">Acción<select id="nAcc"><option value="bloquear">Bloquear</option><option value="permitir">Permitir</option></select></label>
        <label class="campo">Servicio<select id="nSrv">${servicios.map((s) => `<option value="${esc(s.id)}">${esc(s.texto)}</option>`).join("")}</select></label>
        <label class="campo">Equipos de la oficina<select id="nOt"><option value="una">Un equipo</option><option value="rango">Un rango de IPs</option><option value="cualquiera">Todos</option></select></label>
        ${campo("nOd", "IP (o desde)", "", "192.168.1.60")}${campo("nOh", "Hasta", "", "192.168.1.70")}
        <label class="campo">Destino en internet<select id="nDt"><option value="cualquiera">Cualquiera</option><option value="una">Una IP</option><option value="rango">Un rango</option></select></label>
        ${campo("nDd", "IP destino (o desde)", "", "")}${campo("nDh", "Hasta", "", "")}</div>
       ${interruptor("nHor", "Solo en un horario", "Si está apagado, la regla vale siempre", false)}
       <div id="nHorBox"><div class="campos">${campo("nHd", "Desde", "08:00", "08:00")}${campo("nHh", "Hasta", "17:00", "17:00")}</div>
        <p class="desc" style="margin:10px 0 4px">Días</p>${diasSelector("nDia", ["1", "2", "3", "4", "5"])}</div>
       ${interruptor("nLog", "Registrar en el log", "Anota cada vez que se aplica la regla", true)}
       <div class="botones"><button class="prim" id="nAdd">Agregar regla</button></div>`);
  const vis = () => {
    $("#nOd").closest("label").style.display = $("#nOt").value === "cualquiera" ? "none" : "";
    $("#nOh").closest("label").style.display = $("#nOt").value === "rango" ? "" : "none";
    $("#nDd").closest("label").style.display = $("#nDt").value === "cualquiera" ? "none" : "";
    $("#nDh").closest("label").style.display = $("#nDt").value === "rango" ? "" : "none";
    $("#nHorBox").style.display = chk("nHor") ? "" : "none";
  };
  ["nOt", "nDt", "nHor"].forEach((i) => $("#" + i).onchange = vis); vis();
  $("#nAdd").onclick = (e) => {
    const d = { accion: $("#nAcc").value, servicio: $("#nSrv").value, origen_tipo: $("#nOt").value, origen_desde: val("nOd"), origen_hasta: val("nOh"),
      destino_tipo: $("#nDt").value, destino_desde: val("nDd"), destino_hasta: val("nDh"), horario: chk("nHor"), desde_hora: val("nHd"), hasta_hora: val("nHh"),
      dias: $$(".nDia:checked").map((c) => +c.value), registrar: chk("nLog") };
    if (d.accion === "bloquear" && d.origen_tipo === "cualquiera") {
      if (!confirm("Vas a bloquear a TODOS los equipos de la oficina. Si el servicio es 'Todo el tráfico' podés quedarte sin acceso al router. ¿Seguro?")) return;
      d.confirmo_todo = true;
    }
    conBoton(e.target, async () => { const x = await api("reglas/agregar", d); toast(x.mensaje, "ok"); ir("reglas"); });
  };
  $$("[data-rdel]").forEach((b) => b.onclick = () => {
    if (!confirm("¿Borrar esta regla?")) return;
    conBoton(b, async () => { const x = await api("reglas/borrar", { num: b.dataset.rdel }); toast(x.mensaje, "ok"); ir("reglas"); });
  });
  $$("[data-ract]").forEach((c) => c.onchange = async () => {
    try { const x = await api("reglas/activar", { num: c.dataset.ract, activa: c.checked }); toast(x.mensaje, "ok"); ir("reglas"); }
    catch (e) { toast(e.message, "mal"); c.checked = !c.checked; }
  });
}

// ---------------------------------------------------------------- FILTRO
async function vFiltro() {
  const f = await api("filtro");
  let dominios = f.dominios.slice(), palabras = f.palabras.slice();
  const lista = (arr, tipo) => arr.length ? arr.map((x, i) => `<span class="etq gris" style="margin:3px;display:inline-flex;gap:6px;align-items:center">${esc(x)}<a href="#" data-q${tipo}="${i}" title="Quitar" aria-label="Quitar" style="display:inline-flex;color:inherit"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg></a></span>`).join("") : `<span class="desc">Vacío</span>`;
  C().innerHTML =
    tarjeta("Sitios bloqueados", "Se bloquea el dominio y todas sus páginas (ej. facebook.com).",
      interruptor("cDom", "Bloquear estos sitios", "", f.dominios_activo) +
      `<div id="cDomL" style="margin:10px 0"></div><div class="fila-inputs">${campo("cDomN", "Agregar sitio", "", "facebook.com")}<button id="cDomA">Agregar</button></div>`) +
    tarjeta("Palabras bloqueadas", "Bloquea direcciones que contengan la palabra (ej. juegos).",
      interruptor("cPal", "Bloquear por palabras", "", f.palabras_activo) +
      `<div id="cPalL" style="margin:10px 0"></div><div class="fila-inputs">${campo("cPalN", "Agregar palabra", "", "casino")}<button id="cPalA">Agregar</button></div>`) +
    tarjeta("Horario", "Cuándo se aplican los bloqueos.",
      interruptor("cHor", "Solo en un horario", "Si está apagado, bloquea siempre", f.horario) +
      `<div id="cHorBox"><div class="campos">${campo("cHd", "Desde", f.desde || "08:00")}${campo("cHh", "Hasta", f.hasta || "17:00")}</div>
       <p class="desc" style="margin:10px 0 4px">Días</p>${diasSelector("cDia", f.dias.includes("7") || !f.dias.length ? ["0", "1", "2", "3", "4", "5", "6"] : f.dias)}</div>`) +
    `<div class="botones"><button class="prim" id="cGuardar">Guardar</button></div>`;
  const pintar = () => {
    $("#cDomL").innerHTML = lista(dominios, "d"); $("#cPalL").innerHTML = lista(palabras, "p");
    $$("[data-qd]").forEach((a) => a.onclick = (e) => { e.preventDefault(); dominios.splice(+a.dataset.qd, 1); pintar(); });
    $$("[data-qp]").forEach((a) => a.onclick = (e) => { e.preventDefault(); palabras.splice(+a.dataset.qp, 1); pintar(); });
  };
  pintar();
  $("#cDomA").onclick = () => { const v = val("cDomN"); if (v) { dominios.push(v); $("#cDomN").value = ""; $("#cDom").checked = true; pintar(); } };
  $("#cPalA").onclick = () => { const v = val("cPalN"); if (v) { palabras.push(v); $("#cPalN").value = ""; $("#cPal").checked = true; pintar(); } };
  const hb = () => $("#cHorBox").style.display = chk("cHor") ? "" : "none";
  $("#cHor").onchange = hb; hb();
  $("#cGuardar").onclick = (e) => conBoton(e.target, async () => {
    const r = await api("filtro", { dominios_activo: chk("cDom"), dominios, palabras_activo: chk("cPal"), palabras, horario: chk("cHor"),
      desde: val("cHd"), hasta: val("cHh"), dias: $$(".cDia:checked").map((c) => +c.value) });
    toast(r.mensaje, "ok"); ir("filtro");
  });
}

// ---------------------------------------------------------------- ANCHO DE BANDA
async function vAncho() {
  const a = await api("ancho");
  const kb = (n) => n ? (n >= 1000 ? (n / 1000).toLocaleString("es-AR") + " Mbit/s" : n + " kbit/s") : "—";
  C().innerHTML =
    (a.modo_rate ? "" : `<div class="aviso amarillo">El router está en modo "por prioridad". Al guardar se pasará a modo "por velocidad" (el que maneja este programa).</div>`) +
    tarjeta("Velocidad de tu conexión", "Poné la velocidad REAL de tu internet (medila en fast.com o speedtest.net). El router reparte en base a esto. 1 Mbit/s = 1000 kbit/s.",
      `<div class="campos">${campo("aSub", "Subida (kbit/s)", a.subida, "ej. 10000", "number", kb(+a.subida))}${campo("aBaj", "Bajada (kbit/s)", a.bajada, "ej. 50000", "number", kb(+a.bajada))}</div>
       <div class="botones"><button class="prim" id="aVel">Guardar velocidad</button></div>`) +
    tarjeta("Reglas", "Garantizá un mínimo o limitá un máximo por equipo y servicio. Máximo 100 reglas.",
      `<table><thead><tr><th>Servicio</th><th>Equipos</th><th>Dirección</th><th>Mínimo</th><th>Máximo</th><th>Activa</th><th></th></tr></thead><tbody>${a.reglas.length ? a.reglas.map((x) =>
        `<tr><td>${esc(x.servicio)}</td><td>${esc(x.equipos)}</td><td>${esc(x.direccion)}</td><td>${kb(x.minimo)}</td><td>${kb(x.maximo)}</td>
         <td>${sw("", x.activa, `data-aact="${esc(x.valor)}"`)}</td><td><button class="chico" data-adel="${esc(x.valor)}">Borrar</button></td></tr>`).join("")
        : `<tr><td colspan="7" class="vacio">Sin reglas: todos comparten la conexión libremente</td></tr>`}</tbody></table>`) +
    tarjeta("Nueva regla", "Ejemplo: que la PC de recepción (192.168.1.60) no use más de 2000 kbit/s de bajada.",
      `<div class="campos">
        <label class="campo">Servicio<select id="aSrv">${a.servicios.map((s) => `<option value="${esc(s.id)}">${esc(s.texto)}</option>`).join("")}</select></label>
        <label class="campo">Equipos<select id="aEt"><option value="una">Un equipo</option><option value="rango">Un rango de IPs</option><option value="todos">Todos</option></select></label>
        ${campo("aDes", "IP (o desde)", "", a.red + ".60")}${campo("aHas", "Hasta", "", a.red + ".70")}
        <label class="campo">Dirección<select id="aDir"><option value="ambas">Subida y bajada</option><option value="bajada">Solo bajada (descargas)</option><option value="subida">Solo subida (envíos)</option></select></label>
        ${campo("aMin", "Mínimo garantizado (kbit/s)", "", "opcional", "number")}${campo("aMax", "Máximo (kbit/s)", "", "ej. 2000", "number")}</div>
       <div class="botones"><button class="prim" id="aAdd">Agregar regla</button></div>`);
  const vis = () => {
    $("#aDes").closest("label").style.display = $("#aEt").value === "todos" ? "none" : "";
    $("#aHas").closest("label").style.display = $("#aEt").value === "rango" ? "" : "none";
  };
  $("#aEt").onchange = vis; vis();
  $("#aVel").onclick = (e) => conBoton(e.target, async () => {
    const r = await api("ancho/velocidad", { subida: val("aSub"), bajada: val("aBaj") }); toast(r.mensaje, "ok"); ir("ancho");
  });
  $("#aAdd").onclick = (e) => conBoton(e.target, async () => {
    const r = await api("ancho/agregar", { servicio: $("#aSrv").value, equipos_tipo: $("#aEt").value, desde: val("aDes"), hasta: val("aHas"),
      direccion: $("#aDir").value, minimo: val("aMin"), maximo: val("aMax") });
    toast(r.mensaje, "ok"); ir("ancho");
  });
  $$("[data-adel]").forEach((b) => b.onclick = () => {
    if (!confirm("¿Borrar esta regla?")) return;
    conBoton(b, async () => { const r = await api("ancho/borrar", { valor: b.dataset.adel }); toast(r.mensaje, "ok"); ir("ancho"); });
  });
  $$("[data-aact]").forEach((c) => c.onchange = async () => {
    try { const r = await api("ancho/activar", { valor: c.dataset.aact, activa: c.checked }); toast(r.mensaje, "ok"); ir("ancho"); }
    catch (er) { toast(er.message, "mal"); c.checked = !c.checked; }
  });
}

// ---------------------------------------------------------------- PUERTOS
async function vPuertos() {
  const p = (await api("puertos")).puertos;
  C().innerHTML = tarjeta("Puertos de red 1 a 8", "Apagá puertos que no se usan o dale prioridad a un equipo importante.",
    `<table><thead><tr><th>Puerto</th><th>Cable</th><th>Encendido</th><th>Prioridad alta</th><th></th></tr></thead><tbody>${p.map((x) =>
      `<tr><td><b>${x.n}</b></td><td>${x.enlace ? '<span class="etq ok">Conectado</span>' : '<span class="etq gris">Sin cable</span>'}</td>
       <td>${sw("pa" + x.n, x.activo)}</td><td>${sw("pp" + x.n, x.prioridad_alta)}</td><td><button class="chico" data-det="${x.n}">Detalle</button></td></tr>`).join("")}</tbody></table>
     <div class="botones"><button class="prim" id="ptGuardar">Guardar</button></div><div id="ptDet"></div>`);
  $$("[data-det]").forEach((b) => b.onclick = async () => {
    try {
      const d = await api("puerto?puerto=" + b.dataset.det);
      $("#ptDet").innerHTML = `<div class="rejilla" style="margin-top:14px">${[["Enlace", d.enlace], ["Velocidad", d.velocidad], ["Dúplex", d.duplex], ["Paquetes recibidos", d.rx_paquetes], ["Paquetes enviados", d.tx_paquetes], ["Errores", d.errores]]
        .map(([k, v]) => `<div class="dato"><span>Puerto ${b.dataset.det} · ${k}</span><b>${esc(v || "—")}</b></div>`).join("")}</div>`;
    } catch (e) { toast(e.message, "mal"); }
  });
  $("#ptGuardar").onclick = (e) => {
    const lista = p.map((x) => ({ n: x.n, activo: chk("pa" + x.n), prioridad_alta: chk("pp" + x.n) }));
    const apagaConCable = lista.filter((x, i) => !x.activo && p[i].activo && p[i].enlace);
    let confirmo = false;
    if (apagaConCable.length) {
      if (!confirm(`El puerto ${apagaConCable.map((x) => x.n).join(", ")} tiene un cable conectado (puede ser el de esta PC). Si lo apagás podés perder la conexión. ¿Seguro?`)) return;
      confirmo = true;
    }
    conBoton(e.target, async () => { const r = await api("puertos", { puertos: lista, confirmo_enlace: confirmo }); toast(r.mensaje, "ok"); ir("puertos"); });
  };
}

// ---------------------------------------------------------------- HERRAMIENTAS
async function vHerramientas() {
  C().innerHTML =
    tarjeta("Probar conexión (ping)", "El router intenta comunicarse con esa dirección. Para probar internet usá 8.8.8.8.",
      `<div class="fila-inputs">${campo("hPing", "Dirección IP", "8.8.8.8")}<button class="prim" id="hPingB">Probar</button></div><div id="hPingR" style="margin-top:12px"></div>`) +
    tarjeta("Buscar dominio (DNS)", "Comprueba que el router pueda traducir nombres a direcciones.",
      `<div class="fila-inputs">${campo("hDns", "Dominio", "google.com")}<button class="prim" id="hDnsB">Buscar</button></div><div id="hDnsR" style="margin-top:12px"></div>`) +
    tarjeta("Registro del router", "",
      `<div class="fila-inputs"><label class="campo">Tipo<select id="hLogT"><option value="sistema">Sistema e inicios de sesión</option><option value="entrante">Conexiones bloqueadas desde internet</option><option value="saliente">Conexiones salientes</option></select></label><button id="hLogB">Ver</button></div>
       <div id="hLogR" style="margin-top:12px"></div>`);
  const res = (ok, txt) => `<div class="aviso ${ok ? "azul" : "amarillo"}">${txt}</div>`;
  $("#hPingB").onclick = (e) => { $("#hPingR").innerHTML = '<p class="desc">Probando… (hasta 20 segundos)</p>'; conBoton(e.target, async () => {
    try { const r = await api("ping", { destino: val("hPing") }); $("#hPingR").innerHTML = res(r.ok, `<b>${r.estado}</b> — ${esc(r.resumen)}${r.promedio_ms ? ` · tiempo promedio ${r.promedio_ms} ms` : ""}`); }
    catch (er) { $("#hPingR").innerHTML = ""; throw er; } }); };
  $("#hDnsB").onclick = (e) => { $("#hDnsR").innerHTML = '<p class="desc">Buscando…</p>'; conBoton(e.target, async () => {
    try { const r = await api("dns", { nombre: val("hDns") }); $("#hDnsR").innerHTML = res(r.ok, esc(r.resumen)); }
    catch (er) { $("#hDnsR").innerHTML = ""; throw er; } }); };
  const verLog = async () => {
    $("#hLogR").innerHTML = '<p class="desc">Leyendo…</p>';
    try {
      const r = await api("registro?tipo=" + $("#hLogT").value + "&limite=300");
      $("#hLogR").innerHTML = (r.fallos_login > 20 ? `<div class="aviso amarillo">Hay <b>${r.fallos_login}</b> intentos fallidos de entrar al router. Conviene cambiar la contraseña.</div>` : "") +
        `<p class="desc">${r.total} entradas${r.hora ? " · hora del router: " + esc(r.hora) : ""} (se muestran las ${Math.min(300, r.total)} más recientes)</p>
         <div style="max-height:420px;overflow:auto"><table><thead><tr><th>Fecha</th><th>Tipo</th><th>Detalle</th></tr></thead><tbody>${r.entradas.map((x) =>
          `<tr><td style="white-space:nowrap">${esc(x.fecha)}</td><td>${esc(x.tipo)}</td><td>${esc(x.mensaje)}</td></tr>`).join("") || '<tr><td colspan="3" class="vacio">Vacío</td></tr>'}</tbody></table></div>`;
    } catch (e) { $("#hLogR").innerHTML = ""; toast(e.message, "mal"); }
  };
  $("#hLogB").onclick = verLog;
}

// ---------------------------------------------------------------- SISTEMA
async function vSistema() {
  const [h, cfg] = await Promise.all([api("hora"), api("config")]);
  C().innerHTML =
    tarjeta("Contraseña del router", "Usá al menos 8 caracteres, sin espacios ni acentos. Guardala en un lugar seguro: si se pierde hay que resetear el router de fábrica.",
      `<div class="campos">${campo("sUs", "Usuario", cfg.usuario, "", "text", "dejalo igual si no querés cambiarlo")}${campo("sAct", "Contraseña actual", "", "", "password")}
       ${campo("sNue", "Contraseña nueva", "", "", "password")}${campo("sRep", "Repetir contraseña nueva", "", "", "password")}</div>
       <div class="botones"><button class="prim" id="sClave">Cambiar contraseña</button></div>`) +
    tarjeta("Fecha y hora", "Necesaria para los horarios de reglas y bloqueos.",
      `<div class="campos"><label class="campo">Zona horaria<select id="sZona">${h.zonas.map(([v, t]) => `<option value="${esc(v)}" ${v === h.zona ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></label>
       ${campo("sNtp", "Servidor de hora (NTP)", h.ntp || "pool.ntp.org")}</div>
       ${interruptor("sVer", "Horario de verano", "En Argentina no se usa", h.verano)}
       <div class="botones"><button class="prim" id="sHora">Guardar</button></div>`) +
    tarjeta("Respaldo de la configuración", "Descarga un archivo con toda la configuración del router. Hacelo antes de cambios grandes.",
      `<div class="botones"><a href="/api/respaldo" download><button class="prim">Descargar respaldo</button></a></div>
       <p class="desc" style="margin-top:10px">Además, este programa guarda automáticamente los valores de cada página antes de modificarla (carpeta <code>respaldos</code>).</p>`) +
    tarjeta("Reiniciar el router", "Internet se corta alrededor de 1 minuto.",
      `<div class="botones"><button class="peligro" id="sReini">Reiniciar router</button></div>`);
  if (h.zona === "4") $("#sZona").insertAdjacentHTML("afterend", '<small style="color:var(--aviso)">La zona actual es la de fábrica (Pacífico, EE.UU.). Para Argentina elegí "Buenos Aires".</small>');
  $("#sClave").onclick = (e) => {
    if (!confirm("¿Cambiar la contraseña del router? Anotala antes de continuar.")) return;
    conBoton(e.target, async () => {
      const r = await api("clave", { usuario: val("sUs") === cfg.usuario ? "" : val("sUs"), actual: $("#sAct").value, nueva: $("#sNue").value, repetir: $("#sRep").value });
      toast(r.mensaje + ". El programa ya usa la nueva.", "ok"); ir("sistema");
    });
  };
  $("#sHora").onclick = (e) => conBoton(e.target, async () => {
    const r = await api("hora", { zona: $("#sZona").value, ntp: val("sNtp"), verano: chk("sVer") }); toast(r.mensaje, "ok"); ir("sistema");
  });
  $("#sReini").onclick = (e) => {
    if (!confirm("¿Reiniciar el router ahora? Internet se cortará alrededor de 1 minuto.")) return;
    conBoton(e.target, async () => {
      const r = await api("reiniciar", { confirmo: true }); toast(r.mensaje, "ok");
      conectado(false, "Reiniciando…");
      setTimeout(() => ir("inicio"), 70000);
    });
  };
}

// ---------------------------------------------------------------- VPN
let sondeoVpn = null;
// Pasos del instalador de SoftEther (las pantallas están en inglés: se muestra el título tal cual aparece)
const _b = (t) => `<span class="tecla">${t}</span>`;
const GUIA_INSTALADOR = `<ol class="guia-inst">
  <li><b>Aviso de Windows</b> "¿Quieres permitir que esta aplicación haga cambios?" → ${_b("Sí")}</li>
  <li><b>Welcome to the SoftEther VPN Setup Wizard</b> → ${_b("Siguiente &gt;")}</li>
  <li><b>Select Software Components to Install</b> → elegí <b>SoftEther VPN Server</b> (el primero de la lista) → ${_b("Siguiente &gt;")}</li>
  <li><b>End User License Agreement</b> → marcá <i>"I agree to the End User License Agreement"</i> → ${_b("Siguiente &gt;")}</li>
  <li><b>Important Notices</b> → ${_b("Siguiente &gt;")}</li>
  <li><b>Directory to Install</b> → dejá la carpeta que viene → ${_b("Siguiente &gt;")}</li>
  <li><b>Ready to Install</b> → ${_b("Siguiente &gt;")} y esperá a que termine</li>
  <li><b>Setup Finished</b> → <b>desmarcá</b> <i>"Start the SoftEther VPN Server Manager"</i> → ${_b("Finalizar")}</li>
  </ol>
  <div class="aviso amarillo" style="margin-top:8px">Si igual se abre el <b>Server Manager</b> y te pide una contraseña, <b>no pongas nada y cerralo</b>: la contraseña la crea el panel. Después volvé acá: el panel detecta la instalación solo y te muestra el botón <b>Configurar automáticamente</b>.</div>`;
async function vVpn() {
  clearInterval(sondeoVpn);
  const v = await api("vpn/estado");
  const si = (b, ok = "Sí", no = "No") => b ? `<span class="etq ok">${ok}</span>` : `<span class="etq mal">${no}</span>`;
  const cab = `<button class="ayuda" id="vAyuda" title="Cómo funciona">?</button>`;
  let h = "";
  if (!v.instalado || v.servicio === "no_instalado") {
    const d = v.descarga;
    h += tarjeta(`Paso 1 · Instalar el servidor VPN ${cab}`,
      `Se instala <b>SoftEther VPN Server ${esc((d.version || v.version).split("-rtm")[0])}</b> (gratis, código libre) en <b>esta PC</b>, que está conectada al router por cable${v.adaptador ? ` (<code>${esc(v.adaptador.nombre)}</code>, ${esc(v.adaptador.ip)})` : ""}. Esta PC tiene que quedar siempre encendida.`,
      (v.adaptador ? "" : `<div class="aviso amarillo">No se encontró una placa de esta PC conectada a la red del router. La VPN necesita una PC conectada por cable al router.</div>`) +
      `<div class="paso"><div class="n">1</div><div><b>Descargar el instalador oficial</b><p>Del sitio oficial de SoftEther (o de GitHub si el sitio está lento). El panel verifica la firma digital antes de usarlo.</p>
         <div id="vProg" style="margin-top:8px"></div><div class="botones" style="margin-top:8px"><button class="prim" id="vDesc" ${d.estado === "listo" ? "disabled" : ""}>${d.estado === "listo" ? "Descargado" : "Descargar (59 MB)"}</button></div></div></div>
       <div class="paso"><div class="n">2</div><div><b>Instalar</b><p>El instalador está en inglés. Seguí estos pasos (son unos 2 minutos):</p>
         ${GUIA_INSTALADOR}
         <div class="botones"><button class="prim" id="vInst" ${d.estado === "listo" ? "" : "disabled"}>Abrir instalador</button></div></div></div>
       <p class="desc" id="vEsperando" style="display:none">Esperando que termine la instalación…</p>`);
  } else if (v.servicio !== "corriendo") {
    h += `<div class="aviso amarillo">SoftEther está instalado pero el servicio está detenido. Reiniciá la PC o iniciá el servicio "SoftEther VPN Server" en Servicios de Windows.</div>`;
  } else if (!v.configurado) {
    h += tarjeta(`Paso 2 · Configurar ${cab}`, "El panel deja todo listo: VPN Azure, SSTP (la VPN de Windows) y el puente a la red del router.",
      `<div class="campos">${campo("vNom", "Nombre para la dirección", "", "ej. oficina-perez", "text", "opcional: queda nombre.vpnazure.net")}</div>
       <div class="botones"><button class="prim" id="vConf">Configurar automáticamente</button></div><div id="vPasos" style="margin-top:12px"></div>`);
  } else {
    const ok = v.azure_conectado && v.sstp && (v.puente || []).length;
    h += (v.error ? `<div class="aviso rojo">${esc(v.error)}</div>` : "") +
      (ok ? `<div class="aviso azul"><b>La VPN está lista.</b> Desde afuera se conecta a <code>${esc(v.direccion)}</code>.</div>`
          : `<div class="aviso amarillo">Falta algo: revisá los puntos en rojo. VPN Azure puede tardar un minuto en conectar (tocá Actualizar).</div>`) +
      tarjeta(`Estado de la VPN ${cab}`, "",
        `<div class="rejilla">
          <div class="dato"><span>Dirección para conectarse</span><b>${esc(v.direccion || "—")}</b></div>
          <div class="dato"><span>Servicio</span><b>${si(v.servicio === "corriendo", "Funcionando", "Detenido")}</b></div>
          <div class="dato"><span>VPN Azure (sin abrir puertos)</span><b>${si(v.azure_conectado, "Conectado", v.azure_activo ? "Conectando…" : "Apagado")}</b></div>
          <div class="dato"><span>VPN de Windows (SSTP)</span><b>${si(v.sstp, "Activa", "Apagada")}</b></div>
          <div class="dato"><span>Puente a la red del router</span><b>${(v.puente || []).length ? `<span class="etq ok">${esc(v.puente[0].adaptador)}</span>` : si(false, "", "Sin puente")}</b></div>
          <div class="dato"><span>IP pública de la oficina</span><b>${esc(v.ip_publica || "—")}</b></div>
        </div>
        <div class="botones"><button id="vReconf">Volver a configurar</button></div>`) +
      tarjeta("Usuarios de la VPN", "Una cuenta por persona. Para conectarse desde Windows 10 usan este usuario y contraseña.",
        `<table><thead><tr><th>Usuario</th><th>Último acceso</th><th>Accesos</th><th></th></tr></thead><tbody>${(v.usuarios || []).length ? v.usuarios.map((u) =>
          `<tr><td><b>${esc(u.nombre)}</b></td><td>${esc(u.ultimo_acceso)}</td><td>${esc(u.accesos)}</td>
           <td style="white-space:nowrap"><a href="/api/vpn/script?usuario=${encodeURIComponent(u.nombre)}" download><button class="chico prim">Archivo para su PC</button></a>
           <button class="chico" data-vcl="${esc(u.nombre)}">Cambiar clave</button> <button class="chico" data-vdel="${esc(u.nombre)}">Borrar</button></td></tr>`).join("")
          : `<tr><td colspan="4" class="vacio">Todavía no hay usuarios</td></tr>`}</tbody></table>
         <div class="fila-inputs" style="margin-top:12px">${campo("vUs", "Usuario nuevo", "", "juan")}${campo("vCl", "Contraseña", "", "mínimo 8", "password")}<button class="prim" id="vAdd">Crear usuario</button></div>`) +
      tarjeta("Cómo se conecta la PC de afuera (Windows 10)", "Opción fácil: descargá el \"Archivo para su PC\" del usuario, pasáselo y que le haga doble clic. Opción manual:",
        `<ol style="margin:0;padding-left:20px;line-height:1.7">
          <li>Inicio → Configuración → Red e Internet → <b>VPN</b> → <b>Agregar una conexión VPN</b></li>
          <li>Proveedor: <b>Windows (integrado)</b> · Nombre: <code>Oficina</code></li>
          <li>Servidor: <code>${esc(v.direccion || "nombre.vpnazure.net")}</code></li>
          <li>Tipo de VPN: <b>Protocolo de túnel de sockets seguros (SSTP)</b></li>
          <li>Inicio de sesión: <b>Nombre de usuario y contraseña</b> → el usuario y la clave de la tabla</li>
          <li>Guardar → <b>Conectar</b>. Para comprobar: abrir <code>http://192.168.1.1</code></li></ol>`);
  }
  C().innerHTML = h;
  $("#vAyuda")?.addEventListener("click", () => abrirModal(AYUDAS.vpn));
  const pintarProg = (p) => {
    const box = $("#vProg"); if (!box) return;
    if (p.estado === "descargando") box.innerHTML = `<div style="background:var(--borde);border-radius:6px;height:10px;overflow:hidden"><div style="height:10px;width:${p.porcentaje}%;background:var(--acento)"></div></div><small class="desc">${p.porcentaje}% · ${(p.bytes / 1e6).toFixed(1)} MB${p.kbs ? " · " + p.kbs + " KB/s" : ""}${p.fuente ? " · desde " + esc(p.fuente) : ""}</small>`;
    else if (p.estado === "verificando") box.innerHTML = `<small class="desc">Verificando firma digital…</small>`;
    else if (p.estado === "listo") box.innerHTML = `<small style="color:var(--ok)">Firma digital verificada${p.firmante ? ": " + esc(p.firmante.split(",")[0].replace("CN=", "")) : ""}${p.version ? " · versión " + esc(p.version) : ""}</small>`;
    else if (p.estado === "error") box.innerHTML = `<div class="aviso rojo">${esc(p.error)}</div>`;
  };
  if (v.descarga) pintarProg(v.descarga);
  $("#vDesc")?.addEventListener("click", async (e) => {
    e.target.disabled = true;
    try {
      pintarProg(await api("vpn/descargar", {}));
      sondeoVpn = setInterval(async () => {
        const p = await api("vpn/progreso").catch(() => null); if (!p) return;
        pintarProg(p);
        if (p.estado === "listo" || p.estado === "error") { clearInterval(sondeoVpn); if (p.estado === "listo") ir("vpn"); else e.target.disabled = false; }
      }, 1000);
    } catch (er) { toast(er.message, "mal"); e.target.disabled = false; }
  });
  $("#vInst")?.addEventListener("click", (e) => {
    // antes de abrir el instalador, se muestra la guía para que nadie arranque sin saber qué hacer
    abrirModal(`<h3>Antes de abrir el instalador</h3>
      <p>Se va a abrir una ventana en inglés. Tené a mano estos pasos:</p>${GUIA_INSTALADOR}
      <div class="botones"><button class="prim" id="vInstOk">Entendido, abrir instalador</button><button onclick="cerrarModal()">Todavía no</button></div>`);
    $("#vInstOk").onclick = (ev) => conBoton(ev.target, async () => {
      const r = await api("vpn/instalar", {}); toast(r.mensaje, "ok");
      cerrarModal();
      $("#vEsperando").style.display = "";
      sondeoVpn = setInterval(async () => {
        const s = await api("vpn/estado").catch(() => null);
        if (s && s.servicio === "corriendo") { clearInterval(sondeoVpn); toast("SoftEther instalado", "ok"); ir("vpn"); }
      }, 4000);
    });
  });
  const configurar = (btn, nombre) => conBoton(btn, async () => {
    const r = await api("vpn/configurar", { nombre });
    if ($("#vPasos")) $("#vPasos").innerHTML = `<div class="aviso azul">${r.pasos.map(esc).join("<br>")}</div>`;
    toast(r.mensaje, "ok"); setTimeout(() => ir("vpn"), 2500);
  });
  $("#vConf")?.addEventListener("click", (e) => configurar(e.target, val("vNom")));
  $("#vReconf")?.addEventListener("click", (e) => {
    const n = prompt("Nombre para la dirección (vacío = dejar el actual):", "");
    if (n === null) return; configurar(e.target, n.trim());
  });
  $("#vAdd")?.addEventListener("click", (e) => conBoton(e.target, async () => {
    const r = await api("vpn/usuario/agregar", { nombre: val("vUs"), clave: $("#vCl").value }); toast(r.mensaje, "ok"); ir("vpn");
  }));
  $$("[data-vdel]").forEach((b) => b.onclick = () => {
    if (!confirm(`¿Borrar el usuario ${b.dataset.vdel}? Ya no podrá conectarse.`)) return;
    conBoton(b, async () => { const r = await api("vpn/usuario/borrar", { nombre: b.dataset.vdel }); toast(r.mensaje, "ok"); ir("vpn"); });
  });
  $$("[data-vcl]").forEach((b) => b.onclick = () => {
    const c = prompt(`Nueva contraseña para ${b.dataset.vcl} (mínimo 8 caracteres):`); if (!c) return;
    conBoton(b, async () => { const r = await api("vpn/usuario/clave", { nombre: b.dataset.vcl, clave: c }); toast(r.mensaje, "ok"); });
  });
}

const VISTAS = { inicio: vInicio, internet: vInternet, lan: vLan, dhcp: vDhcp, reenvio: vReenvio, dmz: vDmz, seguridad: vSeguridad,
  reglas: vReglas, filtro: vFiltro, ancho: vAncho, puertos: vPuertos, herramientas: vHerramientas, sistema: vSistema, vpn: vVpn };

ir("inicio");
setInterval(() => fetch("/api/latido").catch(() => {}), 20000);
setInterval(async () => { try { await api("estado"); conectado(true, "Conectado"); } catch (e) { conectado(false, "Sin conexión"); } }, 60000);
