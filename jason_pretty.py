import pprint, sys, json

if __name__ == "__main__":
    json = json.load(sys.stdin)
    pprint.pprint(json)


