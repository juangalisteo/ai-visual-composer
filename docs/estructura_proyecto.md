# Generar árbol limpio del proyecto

## Objetivo

Generar un archivo con la estructura del proyecto sin incluir carpetas pesadas ni archivos temporales.

Se excluyen automáticamente:

- ComfyUI
- .git
- __pycache__
- output
- logs
- estructura_actual.txt
- estructura_limpia.txt
- archivos .pyc
- archivos .pyo

---

## Comando

```powershell
$excludedNames = @(
    "ComfyUI",
    ".git",
    "__pycache__",
    "output",
    "logs",
    "estructura_actual.txt",
    "estructura_limpia.txt"
)

$excludedExtensions = @(
    ".pyc",
    ".pyo"
)

function Write-ProjectTree {
    param(
        [string]$Path,
        [string]$Indent = "",
        [string]$OutputFile
    )

    $items = Get-ChildItem -LiteralPath $Path -Force |
        Where-Object {
            $excludedNames -notcontains $_.Name -and
            $excludedExtensions -notcontains $_.Extension
        } |
        Sort-Object `
            @{ Expression = { -not $_.PSIsContainer } }, `
            Name

    for ($i = 0; $i -lt $items.Count; $i++) {

        $item = $items[$i]

        $isLast = $i -eq ($items.Count - 1)

        $branch = if ($isLast) {
            "\--- "
        }
        else {
            "+--- "
        }

        "$Indent$branch$($item.Name)" |
            Out-File `
                -FilePath $OutputFile `
                -Append `
                -Encoding utf8

        if ($item.PSIsContainer) {

            $nextIndent = if ($isLast) {
                "$Indent    "
            }
            else {
                "$Indent|   "
            }

            Write-ProjectTree `
                -Path $item.FullName `
                -Indent $nextIndent `
                -OutputFile $OutputFile
        }
    }
}

$outputFile = "estructura_proyecto.txt"

"MC_IA/" |
    Out-File `
        -FilePath $outputFile `
        -Encoding utf8

Write-ProjectTree `
    -Path "." `
    -OutputFile $outputFile

Write-Host ""
Write-Host "ÁRBOL LIMPIO GENERADO:"
Write-Host $outputFile
```

---

## Abrir automáticamente

```powershell
code estructura_limpia.txt
```

---

## Resultado

Genera un archivo:

```
estructura_limpia.txt
```

con la estructura real del proyecto, excluyendo todo el contenido pesado y temporal.

Ideal para:

- Revisiones de arquitectura.
- Compartir el proyecto.
- Auditorías.
- Refactorizaciones.
- Documentación.