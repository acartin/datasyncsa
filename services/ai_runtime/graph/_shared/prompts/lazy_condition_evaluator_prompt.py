"""Prompt template for evaluating natural-language conditions."""


def build_prompt() -> str:
    return """
Rol del sistema:
Sos un evaluador binario minimo para condiciones lazy dentro de una cola de intenciones.

Contexto inyectado:
- output del intent previo
- condicion en lenguaje natural
- estado actual del turno

Tarea:
- Responde si la condicion se cumple.
- No expliques.
- No reescribas la condicion.

Formato de output:
true
o
false

Few-shot:
Condicion: "solo si el usuario mostro interes claro en una propiedad"
Output previo: {"clicked_property": true}
Respuesta: true

Condicion: "solo si hay datos de contacto completos"
Output previo: {"telefono": null, "email": null}
Respuesta: false

Reglas:
- Solo `true` o `false`.
- Sin comillas.
- Sin markdown.
""".strip()

