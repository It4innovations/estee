
from simpy import Environment, Event
from .trace import TaskAssignTraceEvent, build_trace_html

from .commands import TaskAssignment
from .runtimeinfo import TaskState, TaskRuntimeInfo, OutputRuntimeInfo


class Simulator:

    def __init__(self, task_graph, workers, scheduler, connector, trace=False):
        self.workers = workers
        self.task_graph = task_graph
        self.connector = connector
        self.scheduler = scheduler
        scheduler.simulator = self
        self.new_finished = []
        self.new_ready = []
        self.wakeup_event = None
        self.env = None
        if trace:
            self.trace_events = []
        else:
            self.trace_events = None

        for i, worker in enumerate(workers):
            assert worker.id is None
            worker.id = i

    def task_info(self, task):
        return self.task_infos[task.id]

    def output_info(self, output):
        return self.output_infos[output.id]

    def add_trace_event(self, trace_event):
        if self.trace_events is not None:
            self.trace_events.append(trace_event)

    def schedule(self, ready_tasks, finished_tasks):
        worker_loads = {}
        schedule = self.scheduler.schedule(ready_tasks, finished_tasks)
        if not schedule:
            return
        schedule.sort(key=lambda a: a.priority, reverse=True)
        for assignment in schedule:
            assert isinstance(assignment, TaskAssignment)
            info = self.task_info(assignment.task)
            if info.state == TaskState.Finished:
                raise Exception("Scheduler tries to assign a finished task ({})"
                                .format(assignment.task))
            if info.state == TaskState.Assigned:
                raise Exception("Scheduler reassigns already assigned task ({})"
                                .format(assignment.task))
            info.state = TaskState.Assigned
            info.assigned_workers.append(assignment.worker)
            worker = assignment.worker
            lst = worker_loads.get(worker)
            if lst is None:
                lst = []
                worker_loads[worker] = lst
            lst.append(assignment)
            self.add_trace_event(TaskAssignTraceEvent(
                self.env.now, assignment.worker, assignment.task))
        for worker in worker_loads:
            worker.assign_tasks(worker_loads[worker])

    def _master_process(self, env):
        self.schedule(self.task_graph.source_tasks(), [])

        while self.unprocessed_tasks > 0:
            self.wakeup_event = Event(env)
            yield self.wakeup_event
            self.schedule(self.new_ready, self.new_finished)
            self.new_finished = []
            self.new_ready = []

    def on_task_finished(self, worker, task):
        info = self.task_info(task)
        assert info.state == TaskState.Assigned
        assert worker in info.assigned_workers
        info.state = TaskState.Finished
        info.end_time = self.env.now
        self.new_finished.append(task)
        self.unprocessed_tasks -= 1

        worker_updates = {}
        for o in task.outputs:
            self.output_info(o).placing.append(worker)
            tasks = sorted(o.consumers, key=lambda t: t.id)
            for t in tasks:
                t_info = self.task_info(t)
                t_info.unfinished_inputs -= 1
                if t_info.unfinished_inputs <= 0:
                    if t_info.unfinished_inputs < 0:
                        raise Exception("Invalid number of unfinished inputs: {}, task {}".format(
                            t_info.unfinished_inputs, t
                        ))
                    assert t_info.unfinished_inputs == 0
                    if t_info.state == TaskState.Waiting:
                        t_info.state = TaskState.Ready
                    self.new_ready.append(t)

            for t in tasks:
                for w in self.task_info(t).assigned_workers:
                    lst = worker_updates.get(w)
                    if lst is None:
                        lst = []
                        worker_updates[w] = lst
                    lst.append(t)

        for w in worker_updates:
            w.update_tasks(worker_updates[w])
        if not self.wakeup_event.triggered:
            self.wakeup_event.succeed()

    def make_trace_report(self, filename):
        build_trace_html(self.trace_events or [], self.workers, filename)

    def run(self):
        assert not self.trace_events

        self.task_infos = [TaskRuntimeInfo(task) for task in self.task_graph.tasks]
        self.output_infos = [OutputRuntimeInfo(task) for task in self.task_graph.outputs]

        self.unprocessed_tasks = self.task_graph.task_count

        env = Environment()
        self.env = env
        self.connector.init(self.env, self.workers)

        for worker in self.workers:
            env.process(worker.run(env, self, self.connector))

        master_process = env.process(self._master_process(env))
        self.scheduler.init(self)

        env.run(master_process)
        return env.now