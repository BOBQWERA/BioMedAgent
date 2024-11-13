
def file_reader(name:str, path:str):

    MAX_CONTENT_SIZE = 2**12
    MAX_LINES = 5
    print(name,path)
    appendix = name.split(".")[-1]
    if appendix not in ["txt","csv","tsv"]:
        return False, None
    if appendix in ["csv","tsv"]:
        with open(path) as f:
            content = f.read()
            if len(content) < MAX_CONTENT_SIZE:
                return True, {
                    "type":"Full Content",
                    "content":content
                }
            
            content = ""
            f.seek(0)
            line_count = 0
            for line in f.readlines():
                if len(line) > MAX_CONTENT_SIZE*2:
                    return False, None
                content += line
                line_count += 1
                line_count
                if len(content) > MAX_CONTENT_SIZE or line_count >= MAX_LINES:
                    return True, {
                        "type":f"First {line_count} rows",
                        "content":content
                    }
        return False, None
    elif appendix == "txt":
        with open(path) as f:
            content = f.read()
            if len(content) < MAX_CONTENT_SIZE:
                return True, {
                    "type":"Full Content",
                    "content":content
                }
            else:
                return True, {
                    "type":"Partial summary",
                    "content":content[:MAX_CONTENT_SIZE]
                }




if __name__ == "__main__":
    print(
        file_reader("TCGA_OV_survival.txt","TCGA_OV_survival.txt")
    )