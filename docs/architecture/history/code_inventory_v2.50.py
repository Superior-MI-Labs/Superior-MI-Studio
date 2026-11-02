"""Produce a reproducible static, non-executing source inventory for the v2.50 Studio archive.
Usage: python3 assurance/code_inventory.py /path/to/StudioProjectRoot
Does not import application code or invoke user projects. No runtime effect.
"""
import ast
import collections
import json
import pathlib
import sys

def inspect(root):
    modules=root/'studio_native'
    result=[]
    refs=[]
    for path in sorted(modules.glob('*.py')):
        content=path.read_text(encoding='utf-8')
        tree=ast.parse(content,filename=str(path))
        funcs=[]
        classes=[]
        local_imports=[]
        for stmt in ast.walk(tree):
            if isinstance(stmt,(ast.FunctionDef,ast.AsyncFunctionDef)):
                funcs.append({'name':stmt.name,'start':stmt.lineno,'lines':stmt.end_lineno-stmt.lineno+1})
            if isinstance(stmt,ast.ClassDef):
                classes.append({'name':stmt.name,'start':stmt.lineno})
            if isinstance(stmt,ast.ImportFrom):
                if stmt.level and stmt.module and (modules/f'{stmt.module.split(".")[0]}.py').exists():
                    local_imports.append(stmt.module.split('.')[0])
                elif stmt.level and not stmt.module:
                    local_imports.extend(x.name for x in stmt.names if (modules/f'{x.name}.py').exists())
            if isinstance(stmt,ast.Import):
                local_imports.extend(a.name.split('.')[1] for a in stmt.names if a.name.startswith('studio_native.') and len(a.name.split('.'))>1)
        local_imports=sorted(set(local_imports))
        refs.extend((path.stem,name) for name in local_imports)
        result.append({'module':path.name,'lines':len(content.splitlines()),'classes':classes,
                       'functions':len(funcs),'largest_functions':sorted(funcs,key=lambda x:x['lines'],reverse=True)[:5],
                       'imports_local':local_imports})
    return {'basis':'unexecuted static analysis of supplied v2.50 source only',
            'modules':result,'summary':{'total_modules':len(result),'total_python_lines':sum(x['lines'] for x in result),
                 'module_import_fan_in':dict(collections.Counter(dst for _,dst in refs)),
                 'test_files':len(list((root/'tests').glob('test_*.py')))}}

if __name__=='__main__':
    if len(sys.argv)!=2:
        raise SystemExit('Expected Studio project root')
    print(json.dumps(inspect(pathlib.Path(sys.argv[1])),indent=2))
