import uuid

from lxml import etree as ET

from ..common.taskgraph import TaskGraph


def dax_deserialize(file):
    tasks = {}
    ids = []

    def parse_value(val, convert=None, default=None):
        if val is None:         # value is not present
            if default is not None:
                return default
        elif val == 'None':     # value is present, but unset
            return None
        elif convert:
            return convert(val)
        return val

    root = ET.parse(file).getroot()

    xmlns_prefix = "{{{}}}".format(root.nsmap[None]) if None in root.nsmap else ""

    for job in root.findall("{}job".format(xmlns_prefix)):
        files = job.findall("{}uses".format(xmlns_prefix))

        outputs = [
            {"name": f.get("file"),
             "size": parse_value(f.get("size"), float, 1),
             "expected_size": parse_value(f.get("expectedSize"), float, None)
             }
            for f in files if f.get("link") == "output"
        ]
        inputs = [f.get("file") for f in files if f.get("link") == "input"]

        id = job.get("id")
        assert id
        ids.append(id)

        name = job.get("name", id)

        cpus = parse_value(job.get("cores", 1), int, 1)
        duration = parse_value(job.get("runtime"), float, 1)
        expected_duration = parse_value(job.get("expectedRuntime"), float, None)

        assert id not in tasks
        tasks[id] = {
            "name": name,
            "duration": duration,
            "expected_duration": expected_duration,
            "cpus": cpus,
            "outputs": outputs,
            "inputs": inputs
        }

    for child in root.findall("{}child".format(xmlns_prefix)):
        child_task = tasks[child.get("ref")]

        parents = [tasks[p.get("ref")] for p in child.findall("{}parent".format(xmlns_prefix))]
        for parent in parents:
            if not set(child_task["inputs"]).intersection([o["name"] for o in parent["outputs"]]):
                name = uuid.uuid4().hex
                parent["outputs"].append({
                    "name": name,
                    "size": 0.0,
                    "expected_size": 0.0
                })
                child_task["inputs"].append(name)

    tg = TaskGraph()
    task_outputs = {}
    task_by_id = {}

    for id in ids:
        definition = tasks[id]
        task = tg.new_task(name=definition["name"],
                           duration=definition["duration"],
                           expected_duration=definition["expected_duration"],
                           cpus=definition["cpus"],
                           outputs=[o["size"] for o in definition["outputs"]])
        for (output, parsed_output) in zip(task.outputs, definition["outputs"]):
            output.expected_size = parsed_output["expected_size"]

        for (index, o) in enumerate(definition["outputs"]):
            assert o["name"] not in task_outputs
            task_outputs[o["name"]] = task.outputs[index]
        task_by_id[id] = task

    for id in ids:
        task = task_by_id[id]
        for input in tasks[id]["inputs"]:
            if input in task_outputs:
                task.add_input(task_outputs[input])

    tg.validate()

    return tg


def dax_serialize(task_graph, file):
    doc = ET.Element("adag")

    task_to_id = {}

    for task in task_graph.tasks:
        id = "task-{}".format(len(task_to_id))
        task_tree = ET.SubElement(doc, "job",
                                  id=id,
                                  name=task.name,
                                  runtime=str(task.duration),
                                  expectedRuntime=str(task.expected_duration),
                                  cores=str(task.cpus))
        for (index, output) in enumerate(task.outputs):
            name = "{}-o{}".format(id, index)
            ET.SubElement(task_tree, "uses",
                          link="output",
                          size=str(output.size),
                          expectedSize=str(output.expected_size),
                          file=name)
        task_to_id[task] = (id, task_tree)

    for task in task_graph.tasks:
        (_, tree) = task_to_id[task]
        inputs = sorted(task.inputs, key=lambda i: task_to_id[i.parent][0])
        for (index, input) in enumerate(inputs):
            parent = input.parent
            (id, _) = task_to_id[parent]
            name = "{}-o{}".format(id, parent.outputs.index(input))
            ET.SubElement(tree, "uses",
                          link="input",
                          size=str(input.size),
                          expectedSize=str(input.expected_size),
                          file=name)

    for task in task_graph.tasks:
        if task.inputs:
            elem = ET.SubElement(doc, "child", ref=task_to_id[task][0])
            parents = sorted({i.parent for i in task.inputs}, key=lambda t: task_to_id[t][0])
            for parent in parents:
                ET.SubElement(elem, "parent", ref=task_to_id[parent][0])

    tree = ET.ElementTree(doc)
    tree.write(file, pretty_print=True, xml_declaration=True, encoding="utf-8")
