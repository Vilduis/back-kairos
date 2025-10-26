
MAPA_CARRERAS = {
    "Tecnología": [
        "Ingeniería de Software",
        "Ciencia de Datos",
        "Ciberseguridad",
        "Ingeniería en Redes y Telecomunicaciones",
        "Desarrollo Web y Móvil (Full-Stack)",
        "Inteligencia Artificial y Machine Learning",
        "Ingeniería en Mecatrónica"
    ],
    
    "Ciencias Sociales": [
        "Psicología",
        "Sociología",
        "Antropología",
        "Trabajo Social",
        "Ciencias Políticas",
        "Relaciones Internacionales",
        "Historia",
        "Derecho" # (A veces se considera una categoría propia)
    ],
    
    "Arte y Diseño": [
        "Diseño Gráfico",
        "Diseño de Modas",
        "Artes Visuales (Pintura, Escultura)",
        "Diseño Industrial",
        "Arquitectura",
        "Comunicación Audiovisual y Cine",
        "Diseño de Interiores",
        "Música"
    ],
    
    "Ciencias Naturales": [
        "Biología",
        "Química",
        "Física",
        "Geología",
        "Ciencias Ambientales",
        "Biotecnología",
        "Matemáticas Puras / Estadística"
    ],
    
    "Negocios y Economía": [
        "Administración de Empresas",
        "Contabilidad y Finanzas",
        "Marketing (Mercadotecnia)",
        "Economía",
        "Negocios Internacionales",
        "Gestión de Recursos Humanos",
        "Logística y Cadena de Suministro"
    ]
    
    # Añade más categorías si tu modelo las predice
}


def obtener_carreras_por_tipo(tipo_carrera):
    """
    Devuelve la lista de carreras para un tipo dado.
    Si el tipo no se encuentra, devuelve una lista vacía.
    """
    return MAPA_CARRERAS.get(tipo_carrera, [])