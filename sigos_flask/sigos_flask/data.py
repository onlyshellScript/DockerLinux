# Datos de ejemplo (portados de src/data/mockData.ts)
ORDERS = [
  {
    "id": "OS-0142",
    "client": "Juan Pérez García",
    "address": "Calle Los Álamos 342, Miraflores",
    "zone": "Zona Norte",
    "installationType": "Instalación doméstica",
    "technician": "Carlos Mendez",
    "visitDate": "17/09/2026",
    "visitTime": "09:00",
    "status": "Pendiente",
    "priority": "Alta",
    "notes": "Cliente solicita instalación urgente por vencimiento de contrato."
  },
  {
    "id": "OS-0141",
    "client": "María López Ruiz",
    "address": "Av. Simón Bolívar 1204, San Borja",
    "zone": "Zona Sur",
    "installationType": "Cambio de medidor",
    "technician": "Roberto Silva",
    "visitDate": "18/09/2026",
    "visitTime": "10:30",
    "status": "Programada",
    "priority": "Media",
    "notes": "Medidor con lectura inconsistente desde julio."
  },
  {
    "id": "OS-0140",
    "client": "Empresa Textil Andina SAC",
    "address": "Zona Industrial Norte Km 3, Ate",
    "zone": "Zona Industrial",
    "installationType": "Instalación industrial",
    "technician": "Luis Vargas",
    "visitDate": "17/09/2026",
    "visitTime": "08:00",
    "status": "En proceso",
    "priority": "Alta",
    "notes": "Instalación para planta de producción. Requiere aprobación de ingeniería."
  },
  {
    "id": "OS-0139",
    "client": "Ana Morales Díaz",
    "address": "Jr. Las Flores 89, Surco",
    "zone": "Zona Sur",
    "installationType": "Revisión de tuberías",
    "technician": "Carmen Torres",
    "visitDate": "16/09/2026",
    "visitTime": "14:00",
    "status": "Completada",
    "priority": "Baja",
    "notes": ""
  },
  {
    "id": "OS-0138",
    "client": "Restaurante El Buen Sabor",
    "address": "Av. Central 567, Miraflores",
    "zone": "Zona Centro",
    "installationType": "Instalación comercial",
    "technician": "Carlos Mendez",
    "visitDate": "20/09/2026",
    "visitTime": "11:00",
    "status": "Programada",
    "priority": "Alta",
    "notes": "Requiere técnico con certificación para locales comerciales."
  },
  {
    "id": "OS-0137",
    "client": "Pedro Quispe Mamani",
    "address": "Pasaje Los Pinos 12, Villa El Salvador",
    "zone": "Zona Sur",
    "installationType": "Instalación doméstica",
    "technician": "Roberto Silva",
    "visitDate": "15/09/2026",
    "visitTime": "09:30",
    "status": "Completada",
    "priority": "Media",
    "notes": ""
  },
  {
    "id": "OS-0136",
    "client": "Clínica San Rafael",
    "address": "Av. Universitaria 2340, San Miguel",
    "zone": "Zona Oeste",
    "installationType": "Instalación hospitalaria",
    "technician": "Luis Vargas",
    "visitDate": "19/09/2026",
    "visitTime": "07:30",
    "status": "Programada",
    "priority": "Alta",
    "notes": "Instalación en área de UCI. Requiere coordinación con jefe de mantenimiento."
  },
  {
    "id": "OS-0135",
    "client": "Hotel Mirador del Pacífico",
    "address": "Jr. Cusco 890, Miraflores",
    "zone": "Zona Centro",
    "installationType": "Cambio de quemadores",
    "technician": "Diego Ramírez",
    "visitDate": "21/09/2026",
    "visitTime": "08:00",
    "status": "Pendiente",
    "priority": "Media",
    "notes": "Quemadores de cocina industrial con falla de encendido."
  }
]

TECHNICIANS = [
  {
    "id": "T-01",
    "name": "Carlos Mendez",
    "phone": "+51 987 654 321",
    "status": "Disponible",
    "ordersCount": 3,
    "nextVisit": "Hoy 11:00",
    "zone": "Zona Centro / Norte",
    "completedToday": 1,
    "avatar": "CM"
  },
  {
    "id": "T-02",
    "name": "Roberto Silva",
    "phone": "+51 976 543 210",
    "status": "Ocupado",
    "ordersCount": 5,
    "nextVisit": "Hoy 14:30",
    "zone": "Zona Sur",
    "completedToday": 2,
    "avatar": "RS"
  },
  {
    "id": "T-03",
    "name": "Luis Vargas",
    "phone": "+51 965 432 109",
    "status": "Disponible",
    "ordersCount": 2,
    "nextVisit": "Mañana 07:30",
    "zone": "Zona Industrial / Oeste",
    "completedToday": 0,
    "avatar": "LV"
  },
  {
    "id": "T-04",
    "name": "Carmen Torres",
    "phone": "+51 954 321 098",
    "status": "Fuera de servicio",
    "ordersCount": 1,
    "nextVisit": "22/09/2026",
    "zone": "Zona Centro",
    "completedToday": 0,
    "avatar": "CT"
  },
  {
    "id": "T-05",
    "name": "Diego Ramírez",
    "phone": "+51 943 210 987",
    "status": "Disponible",
    "ordersCount": 4,
    "nextVisit": "Hoy 15:00",
    "zone": "Zona Este",
    "completedToday": 2,
    "avatar": "DR"
  },
  {
    "id": "T-06",
    "name": "Sandra Huamán",
    "phone": "+51 932 109 876",
    "status": "Ocupado",
    "ordersCount": 3,
    "nextVisit": "Hoy 16:00",
    "zone": "Zona Oeste",
    "completedToday": 1,
    "avatar": "SH"
  }
]

MATERIALS = [
  {
    "id": "M-001",
    "name": "Tubo de cobre 1/2\"",
    "code": "TC-012",
    "unit": "metro",
    "stock": 145,
    "minStock": 50,
    "stockStatus": "OK",
    "lastUpdated": "14/09/2026"
  },
  {
    "id": "M-002",
    "name": "Válvula de corte 3/4\"",
    "code": "VC-034",
    "unit": "unidad",
    "stock": 32,
    "minStock": 40,
    "stockStatus": "Bajo",
    "lastUpdated": "15/09/2026"
  },
  {
    "id": "M-003",
    "name": "Medidor G4 residencial",
    "code": "MG-004",
    "unit": "unidad",
    "stock": 18,
    "minStock": 20,
    "stockStatus": "Bajo",
    "lastUpdated": "16/09/2026"
  },
  {
    "id": "M-004",
    "name": "Fitting codo 90° 1/2\"",
    "code": "FC-009",
    "unit": "unidad",
    "stock": 287,
    "minStock": 100,
    "stockStatus": "OK",
    "lastUpdated": "10/09/2026"
  },
  {
    "id": "M-005",
    "name": "Regulador de presión 1/2\"",
    "code": "RP-012",
    "unit": "unidad",
    "stock": 8,
    "minStock": 15,
    "stockStatus": "Crítico",
    "lastUpdated": "17/09/2026"
  },
  {
    "id": "M-006",
    "name": "Sellador de tuberías (rollo)",
    "code": "ST-100",
    "unit": "rollo",
    "stock": 64,
    "minStock": 30,
    "stockStatus": "OK",
    "lastUpdated": "12/09/2026"
  },
  {
    "id": "M-007",
    "name": "Detector de gas portátil",
    "code": "DG-001",
    "unit": "unidad",
    "stock": 5,
    "minStock": 3,
    "stockStatus": "OK",
    "lastUpdated": "01/09/2026"
  },
  {
    "id": "M-008",
    "name": "Tubo de acero galvanizado 1\"",
    "code": "TA-100",
    "unit": "metro",
    "stock": 12,
    "minStock": 20,
    "stockStatus": "Bajo",
    "lastUpdated": "16/09/2026"
  }
]

USERS = [
  {
    "id": "U-01",
    "name": "Ricardo Paredes",
    "email": "r.paredes@sigos.pe",
    "role": "Administrador",
    "active": True,
    "lastLogin": "Hoy, 08:42",
    "phone": "+51 987 000 001"
  },
  {
    "id": "U-02",
    "name": "Gabriela Soto",
    "email": "g.soto@sigos.pe",
    "role": "Coordinador",
    "active": True,
    "lastLogin": "Hoy, 07:55",
    "phone": "+51 987 000 002"
  },
  {
    "id": "U-03",
    "name": "Carlos Mendez",
    "email": "c.mendez@sigos.pe",
    "role": "Técnico",
    "active": True,
    "lastLogin": "Hoy, 08:10",
    "phone": "+51 987 654 321"
  },
  {
    "id": "U-04",
    "name": "Roberto Silva",
    "email": "r.silva@sigos.pe",
    "role": "Técnico",
    "active": True,
    "lastLogin": "Hoy, 07:48",
    "phone": "+51 976 543 210"
  },
  {
    "id": "U-05",
    "name": "Carmen Torres",
    "email": "c.torres@sigos.pe",
    "role": "Técnico",
    "active": False,
    "lastLogin": "10/09/2026",
    "phone": "+51 954 321 098"
  },
  {
    "id": "U-06",
    "name": "Miguel Fernández",
    "email": "m.fernandez@sigos.pe",
    "role": "Coordinador",
    "active": True,
    "lastLogin": "Ayer, 17:32",
    "phone": "+51 987 000 006"
  }
]

NOTIFICATIONS = [
  {
    "id": "N-01",
    "title": "Orden pendiente de asignación",
    "text": "La orden #OS-0142 requiere un técnico.",
    "time": "Hace 12 min",
    "important": True,
    "read": False,
    "link": "orders"
  },
  {
    "id": "N-02",
    "title": "Stock bajo en inventario",
    "text": "Regulador de presión está en nivel crítico (8 de 15 mín.).",
    "time": "Hace 25 min",
    "important": True,
    "read": False,
    "link": "materials"
  },
  {
    "id": "N-03",
    "title": "Evidencia cargada",
    "text": "Luis Vargas cargó evidencias para OS-0140 (2 fotos).",
    "time": "Hace 45 min",
    "important": False,
    "read": False,
    "link": "order-detail"
  },
  {
    "id": "N-04",
    "title": "Orden completada",
    "text": "La orden OS-0139 fue marcada como completada.",
    "time": "Hace 1 h",
    "important": False,
    "read": False,
    "link": "order-detail"
  },
  {
    "id": "N-05",
    "title": "Nuevo material registrado",
    "text": "Se registraron 50 unidades de tubo de cobre 1/2\".",
    "time": "Hace 2 h",
    "important": False,
    "read": True,
    "link": "materials"
  },
  {
    "id": "N-06",
    "title": "Usuario inactivo",
    "text": "Carmen Torres lleva 7 días sin acceso al sistema.",
    "time": "Ayer",
    "important": False,
    "read": True,
    "link": "users"
  }
]

DEMO_ACCOUNTS = [
  {
    "role": "Administrador",
    "name": "Ricardo Paredes",
    "email": "r.paredes@sigos.pe",
    "password": "admin2026",
    "initials": "RP"
  },
  {
    "role": "Coordinador",
    "name": "Gabriela Soto",
    "email": "g.soto@sigos.pe",
    "password": "coordinador2026",
    "initials": "GS"
  },
  {
    "role": "Técnico",
    "name": "Carlos Mendez",
    "email": "c.mendez@sigos.pe",
    "password": "tecnico2026",
    "initials": "CM"
  }
]

