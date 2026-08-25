# State Estimator

Responsável por transformar evidências em:

- estado latente Z_t ∈ [0,1]^4
- confiança C_t ∈ [0,1]
- incerteza U_t = 1 - C_t
- representação geométrica M_t ∈ B³

O estado latente possui as dimensões:

focus
stress
autonomy
fatigue

A projeção geométrica deve permanecer responsabilidade do Sinapse, não do Dataset.
