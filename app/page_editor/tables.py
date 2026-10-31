"""Sparse table geometry and bounded visual capability; no dense TableMap.

An AVL of disjoint occupied intervals stores each gap before its key and the
subtree's maximum gap. Finding the first free column jumps a whole contiguous
occupied run in logarithmic AVL work. Each real cell is inserted/expired once;
neither declared spans nor virtual area drive loops or memory allocation.
"""
import heapq
import re
from .policy_constants import MAX_UI_TABLE_SLOTS
from .types import PolicyError, TableCapability


def _error(code):raise PolicyError(code)


def _tag(node):
    return node.tag.rsplit('}',1)[-1] if isinstance(node.tag,str) else ''


def _decimal(value):
    if type(value) is not str or not re.fullmatch(r'[1-9][0-9]*',value):_error('TABLE_SPAN_INVALID')
    # Python's decimal-string conversion guard is not a business span limit.
    # Small chunks avoid changing that process-global safety setting.
    number=0
    for offset in range(0,len(value),9):
        chunk=value[offset:offset+9]
        number=number*(10**len(chunk))+int(chunk)
    return number


class _Node:
    __slots__=('start','end','gap','left','right','height','max_gap','last_end')
    def __init__(self,start,end,gap):
        self.start=start;self.end=end;self.gap=gap
        self.left=None;self.right=None;self.height=1
        self.max_gap=gap;self.last_end=end


def _height(node):return node.height if node else 0


def _update(node):
    node.height=1+max(_height(node.left),_height(node.right))
    node.max_gap=max(node.gap,node.left.max_gap if node.left else 0,node.right.max_gap if node.right else 0)
    node.last_end=node.right.last_end if node.right else node.end
    return node


def _rotate_left(node):
    result=node.right;node.right=result.left;result.left=node
    _update(node);return _update(result)


def _rotate_right(node):
    result=node.left;node.left=result.right;result.right=node
    _update(node);return _update(result)


def _balance(node):
    if node is None:return None
    _update(node);difference=_height(node.left)-_height(node.right)
    if difference>1:
        if _height(node.left.left)<_height(node.left.right):node.left=_rotate_left(node.left)
        return _rotate_right(node)
    if difference<-1:
        if _height(node.right.right)<_height(node.right.left):node.right=_rotate_right(node.right)
        return _rotate_left(node)
    return node


def _insert(node,item):
    if node is None:return item
    if item.start<node.start:node.left=_insert(node.left,item)
    elif item.start>node.start:node.right=_insert(node.right,item)
    else:_error('TABLE_GRID_OVERLAP')
    return _balance(node)


def _remove(node,key):
    if node is None:_error('TABLE_PROOF_INVARIANT')
    if key<node.start:node.left=_remove(node.left,key)
    elif key>node.start:node.right=_remove(node.right,key)
    else:
        if node.left is None:return node.right
        if node.right is None:return node.left
        successor=node.right
        while successor.left:successor=successor.left
        node.start,node.end,node.gap=successor.start,successor.end,successor.gap
        node.right=_remove(node.right,successor.start)
    return _balance(node)


def _set_gap(node,key,gap):
    if node is None:_error('TABLE_PROOF_INVARIANT')
    if key<node.start:node.left=_set_gap(node.left,key,gap)
    elif key>node.start:node.right=_set_gap(node.right,key,gap)
    else:node.gap=gap
    return _update(node)


def _neighbours(node,key):
    before=after=equal=None
    while node:
        if key<node.start:after=node;node=node.left
        elif key>node.start:before=node;node=node.right
        else:
            equal=node
            cursor=node.left
            while cursor:
                before=cursor;cursor=cursor.right
            cursor=node.right
            while cursor:
                after=cursor;cursor=cursor.left
            break
    return before,equal,after


def _first_gap_after(node,key):
    if node is None or node.max_gap<=0:return None
    if node.start<=key:return _first_gap_after(node.right,key)
    found=_first_gap_after(node.left,key)
    if found:return found
    if node.gap>0:return node
    return _first_gap_after(node.right,key)


class _Intervals:
    def __init__(self):self.root=None

    def first_free(self,column):
        before,equal,_=_neighbours(self.root,column)
        occupied=equal or (before if before and before.end>column else None)
        if occupied is None:return column
        gap=_first_gap_after(self.root,occupied.start)
        return gap.start-gap.gap if gap else self.root.last_end

    def insert(self,start,end):
        before,equal,after=_neighbours(self.root,start)
        if equal or (before and before.end>start) or (after and after.start<end):_error('TABLE_GRID_OVERLAP')
        gap=start-(before.end if before else 0)
        self.root=_insert(self.root,_Node(start,end,gap))
        if after:self.root=_set_gap(self.root,after.start,after.start-end)

    def remove(self,start):
        before,equal,after=_neighbours(self.root,start)
        if equal is None:_error('TABLE_PROOF_INVARIANT')
        if after:self.root=_set_gap(self.root,after.start,after.start-(before.end if before else 0))
        self.root=_remove(self.root,start)


def _geometry(table):
    groups=[];caption_count=0;head_count=0
    for child in table:
        tag=_tag(child)
        if tag=='caption':caption_count+=1
        elif tag in {'thead','tbody'}:
            if tag=='thead':head_count+=1
            rows=list(child)
            if any(_tag(row)!='tr' for row in rows):_error('TABLE_STRUCTURE_INVALID')
            groups.append(rows)
        else:_error('TABLE_STRUCTURE_INVALID')
    if caption_count>1 or head_count>1:_error('TABLE_STRUCTURE_INVALID')
    row_count=sum(len(group) for group in groups);cell_count=0;max_columns=0
    for rows in groups:
        occupied=_Intervals();expirations=[]
        for row_index,row in enumerate(rows):
            while expirations and expirations[0][0]<=row_index:
                _,start=heapq.heappop(expirations);occupied.remove(start)
            column=0
            for cell in row:
                if _tag(cell) not in {'td','th'}:_error('TABLE_STRUCTURE_INVALID')
                cell_count+=1
                rowspan_value=cell.attrib.get('rowspan','1')
                if not re.fullmatch(r'[1-9][0-9]*',rowspan_value):_error('TABLE_SPAN_INVALID')
                remaining=str(len(rows)-row_index)
                if len(rowspan_value)>len(remaining) or (len(rowspan_value)==len(remaining) and rowspan_value>remaining):_error('TABLE_ROWSPAN_OUTSIDE_GROUP')
                rowspan=int(rowspan_value)
                colspan=_decimal(cell.attrib.get('colspan','1'))
                column=occupied.first_free(column);end=column+colspan
                occupied.insert(column,end)
                heapq.heappush(expirations,(row_index+rowspan,column))
                column=end;max_columns=max(max_columns,end)
    return row_count,cell_count,max_columns


def inspect_tables(tree, *, remaining_budget=MAX_UI_TABLE_SLOTS):
    """Validate every actual table, returning GUI facts without altering HTML.

    Geometry permits ragged rows. Rowspans must remain in their real row group;
    positive colspans may be arbitrarily large. Both outer/inner nested tables
    are opaque. Budget is aggregate remaining GUI work, not a storage quota.
    """
    if type(remaining_budget) is not int or not 0<=remaining_budget<=MAX_UI_TABLE_SLOTS:_error('TABLE_BUDGET_INVALID')
    tables=[];nested=set();stack=[(tree,())]
    while stack:
        node,ancestors=stack.pop()
        if _tag(node)=='table':
            if ancestors:nested.add(id(node));nested.update(id(item) for item in ancestors)
            tables.append(node);ancestors=ancestors+(node,)
        stack.extend((child,ancestors) for child in reversed(list(node)))
    facts=[]
    for index,table in enumerate(tables):
        rows,cells,columns=_geometry(table)
        cost=rows*columns if rows and columns<=MAX_UI_TABLE_SLOTS//rows else 0 if not rows else None
        is_nested=id(table) in nested
        if is_nested:reason='nested'
        elif not rows or not columns:reason='empty'
        elif cost is None:reason='oversized'
        elif cost>remaining_budget:reason='aggregate-budget'
        else:reason='rich'
        rich=reason=='rich'
        if rich:remaining_budget-=cost
        facts.append(TableCapability(index,rows,cells,is_nested,rich,reason,cost))
    return tuple(facts)
