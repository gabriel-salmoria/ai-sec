Valores em %.

| Modelo | Prompt | Teste | CER | WER | CER nomes | CER raros | CER inéditos | Nomes exatos |
|---|---|---|---|---|---|---|---|---|
| base | chandra | test_bressay | 20,1 | 34,1 | 20,9 | 20,4 | 28,8 | 66,4 |
| base | nosso | test_bressay | 19,8 | 33,9 | 18,6 | 17,0 | 28,3 | 68,1 |
| base_fp8 | chandra | test_bressay | 20,2 | 34,4 | 20,4 | 18,5 | 30,1 | 68,1 |
| base_fp8 | nosso | test_bressay | 21,0 | 35,6 | 19,1 | 18,6 | 27,0 | 68,2 |
| ft | chandra | test_bressay | 4,9 | 11,6 | 10,9 | 10,6 | 21,7 | 79,0 |
| ft | nosso | test_bressay | 4,9 | 11,5 | 11,0 | 10,8 | 21,2 | 78,4 |
| ft_fp8 | chandra | test_bressay | 5,0 | 11,7 | 10,7 | 10,7 | 24,3 | 79,1 |
| ft_fp8 | nosso | test_bressay | 4,9 | 11,5 | 10,8 | 10,6 | 21,2 | 79,0 |
| base | chandra | test_sintetico | 8,6 | 21,4 | 8,6 | 9,4 | 9,4 | 74,6 |
| base | nosso | test_sintetico | 6,2 | 18,8 | 8,0 | 8,8 | 8,9 | 75,8 |
| base_fp8 | chandra | test_sintetico | 9,5 | 21,9 | 9,0 | 9,4 | 9,4 | 74,6 |
| base_fp8 | nosso | test_sintetico | 6,4 | 19,1 | 8,3 | 9,2 | 9,2 | 75,6 |
| ft | chandra | test_sintetico | 3,4 | 10,7 | 4,7 | 5,5 | 5,5 | 83,6 |
| ft | nosso | test_sintetico | 3,3 | 10,6 | 4,7 | 5,5 | 5,5 | 83,7 |
| ft_fp8 | chandra | test_sintetico | 3,4 | 10,7 | 4,7 | 5,5 | 5,5 | 83,5 |
| ft_fp8 | nosso | test_sintetico | 3,4 | 10,7 | 4,7 | 5,6 | 5,6 | 83,5 |
