// ckeditor.js (entry point before build)

import ClassicEditorBase from '@ckeditor/ckeditor5-editor-classic/src/classiceditor';

// Standard plugins
import Essentials from '@ckeditor/ckeditor5-essentials/src/essentials';
import Bold from '@ckeditor/ckeditor5-basic-styles/src/bold';
import Italic from '@ckeditor/ckeditor5-basic-styles/src/italic';
import Underline from '@ckeditor/ckeditor5-basic-styles/src/underline';
import Heading from '@ckeditor/ckeditor5-heading/src/heading';
import Link from '@ckeditor/ckeditor5-link/src/link';
import List from '@ckeditor/ckeditor5-list/src/list';
import BlockQuote from '@ckeditor/ckeditor5-block-quote/src/blockquote';
import CodeBlock from '@ckeditor/ckeditor5-code-block/src/codeblock';
import Image from '@ckeditor/ckeditor5-image/src/image';
import ImageUpload from '@ckeditor/ckeditor5-image/src/imageupload';
import MediaEmbed from '@ckeditor/ckeditor5-media-embed/src/mediaembed';
import Table from '@ckeditor/ckeditor5-table/src/table';
import TableToolbar from '@ckeditor/ckeditor5-table/src/tabletoolbar';

// 🧪 MathType plugin from WIRIS (Premium plugin)
import MathType from '@wiris/mathtype-ckeditor5';

export default class ClassicEditor extends ClassicEditorBase {}

ClassicEditor.builtinPlugins = [
    Essentials,
    Bold,
    Italic,
    Underline,
    Heading,
    Link,
    List,
    BlockQuote,
    CodeBlock,
    Image,
    ImageUpload,
    MediaEmbed,
    Table,
    TableToolbar,
    MathType  // <-- Include MathType (adds both mathType and chemType buttons)
];

ClassicEditor.defaultConfig = {
    toolbar: {
        items: [
            'heading',
            '|', 'bold', 'italic', 'underline',
            '|', 'link', 'bulletedList', 'numberedList',
            '|', 'insertTable', 'mediaEmbed',
            '|', 'mathType', 'chemType',  // <- Toolbar buttons
            '|', 'blockQuote', 'codeBlock',
            '|', 'undo', 'redo'
        ]
    },
    language: 'en',
    table: {
        contentToolbar: ['tableColumn', 'tableRow', 'mergeTableCells']
    }
};
