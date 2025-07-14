from pathlib import Path
from typing import Any, Dict, List

from nicegui import ui
from nicegui.events import GenericEventArguments

from ..element.red import notify
from .edit_page import edit_page
from ..utils.utils import get_task
from ..rename.process import Rename
from ..utils.path import TASK_PATH, RECORD_PATH


@ui.refreshable
def create_table():
    rows = []
    columns: List[Dict[str, Any]] = [
        {'name': 'id', 'label': 'ID', 'field': 'id'},
        {'name': 'value', 'label': '操作', 'field': 'value'},
        {'name': 'path', 'label': '传入路径', 'field': 'path'},
        {'name': 'name', 'label': '识别剧集', 'field': 'name'},
        {'name': 'season', 'label': '季度', 'field': 'season'},
        {'name': 'status', 'label': '状态', 'field': 'status'},
        {'name': 'uuid', 'label': 'UUID', 'field': 'uuid'},
        {'name': 'is_anime', 'label': '是否为动漫', 'field': 'is_anime'},
        {'name': 'is_movie', 'label': '是否为电影', 'field': 'is_movie'},
        {'name': 'ai_used', 'label': 'AI识别', 'field': 'ai_used'},
    ]
    for j in columns:
        j['align'] = 'center'
        j['sortable'] = True

    sorted_files = sorted(
        TASK_PATH.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True
    )
    for index, i in enumerate(sorted_files):
        task_data = get_task(i.stem)
        if task_data['error']:
            status = task_data['error']
        else:
            status = '成功'

        # 检查是否使用了AI
        ai_used = task_data.get('use_ai', False)
        ai_status = '是' if ai_used else '否'

        rows.append(
            {
                'id': index,
                'path': task_data['path'],
                'name': task_data['name'],
                'uuid': task_data['uuid'],
                'season': task_data['season_id'],
                'status': status,
                'is_anime': task_data['is_anime'],
                'is_movie': task_data['is_movie'],
                'ai_used': ai_status,
                'value': '操作',
            }
        )

    table = (
        ui.table(columns=columns, rows=rows)
        .classes('w-full h-full rounded')
        .style('max-height: 90%; border-radius: 10px;separator: cell')
    )
    table._props['visible-columns'] = [
        'id',
        'path',
        'name',
        'season',
        'status',
        'ai_used',
        'value',
    ]

    table.add_slot(
        'body-cell-value',
        """
        <q-td :props="props">
            <q-btn @click="$parent.$emit('retry', props)" label="重试" color='green-6' class="q-mr-sm rounded" style="border-radius: 5rem"/>
            <q-btn @click="$parent.$emit('edit', props)" label="编辑" color='blue-6' class="q-mr-sm rounded" style="border-radius: 5rem"/>
            <q-btn @click="$parent.$emit('del', props)" label="删除" color='red-6' class="q-mr-sm rounded" style="border-radius: 5rem"/>
        </q-td>
    """,  # noqa: E501
    )

    table.add_slot(
        'body-cell-id',
        '''
        <q-td
            :props="props"
            :class="{
            'bg-green-4 text-white': props.row.status === '成功',
            'bg-red-4 text-white': props.row.status !== '成功'
            }"
        >
        {{props.value}}
        </q-td>''',  # noqa: E501
    )

    table.on('action', lambda msg: print(msg))
    table.on('retry', lambda ev: handle_retry(ev))
    table.on('edit', lambda ev: handle_edit(ev))
    table.on('del', lambda ev: handle_delete(ev))


async def handle_edit(ev: GenericEventArguments):
    arg = ev.args
    uuid = arg['row']['uuid']
    await edit_page(uuid)
    create_table.refresh()


def handle_retry(ev: GenericEventArguments):
    arg = ev.args
    row_data = arg['row']
    path = row_data['path']
    is_anime = row_data['is_anime']
    is_movie = row_data['is_movie']
    data = Rename().process(Path(path), is_anime, is_movie)
    if isinstance(data, str):
        notify(data)
    else:
        notify('重新开始任务！')
    handle_delete(ev, is_notify=False)


def handle_delete(ev: GenericEventArguments, is_notify: bool = True):
    arg = ev.args
    row_data = arg['row']
    uuid = row_data['uuid']

    path1 = TASK_PATH / f'{uuid}.json'
    path2 = RECORD_PATH / f'{uuid}.json'

    if path1.exists():
        path1.unlink()
    if path2.exists():
        path2.unlink()

    if is_notify:
        notify(f'删除任务记录{uuid}成功!')

    create_table.refresh()
